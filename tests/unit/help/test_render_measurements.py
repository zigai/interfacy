from __future__ import annotations

import pytest

from interfacy.common.terminal import strip_ansi
from interfacy.declarations.executable_flags import ExecutableFlag
from interfacy.help import Aligned, HelpLayout, StandardLayout
from interfacy.help.content import HelpContent, HelpContext, default_help_renderer
from interfacy.help.renderer import SchemaHelpRenderer
from interfacy.schema.model import (
    Argument,
    ArgumentDefault,
    ArgumentKind,
    Command,
    ParserSchema,
    ValueShape,
)
from interfacy.schema.values import ValueCardinality
from tests.fixtures.terminal import freeze_terminal


def _command(default: str, *, flag: str = "--value") -> Command:
    argument = Argument(
        name="value",
        display_name="value",
        kind=ArgumentKind.OPTION,
        value_shape=ValueShape.SINGLE,
        flags=(flag,),
        required=False,
        cardinality=ValueCardinality(0, 1, 1),
        argument_default=ArgumentDefault.present(default),
        help="Value used when the command runs.",
        type=str,
        parser=None,
    )
    return Command(
        obj=None,
        canonical_name="demo",
        cli_name="demo",
        aliases=(),
        raw_description="Render this description consistently at the requested terminal width.",
        parameters=[argument],
    )


def test_explicit_renderer_width_controls_layout_and_description_measurement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = _command("abcdefghijklmnopqrstuvwxyz")
    layout = Aligned(default_field_width_max=None, default_overflow_mode="newline")
    renderer = SchemaHelpRenderer(layout, terminal_width=72)

    freeze_terminal(monkeypatch, 50)
    narrow_terminal = renderer.render_command_help(command, "demo")
    freeze_terminal(monkeypatch, 160)
    wide_terminal = renderer.render_command_help(command, "demo")

    assert narrow_terminal == wide_terminal
    assert all(len(line) <= 72 for line in strip_ansi(narrow_terminal).splitlines())


def test_reused_layout_takes_current_configured_widths_without_previous_measurements() -> None:
    template = "{flag_col}[{default_padded}] {description}"
    layout = HelpLayout(
        format_option=template,
        include_metavar_in_flag_display=False,
        default_field_width=7,
        pos_flag_width=12,
    )
    renderer = SchemaHelpRenderer(layout, terminal_width=160)
    renderer.render_command_help(_command("a long default", flag="--a-long-option-name"), "demo")

    layout.default_field_width = 18
    layout.pos_flag_width = 40
    reused = renderer.render_command_help(_command("x"), "demo")
    fresh = SchemaHelpRenderer(
        HelpLayout(
            format_option=template,
            include_metavar_in_flag_display=False,
            default_field_width=18,
            pos_flag_width=40,
        ),
        terminal_width=160,
    ).render_command_help(_command("x"), "demo")

    assert reused == fresh


def test_implicit_width_follows_terminal_and_explicit_assignment_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rendered_widths: list[int] = []

    def finalize(context: HelpContext, content: HelpContent) -> str:
        rendered_widths.append(context.terminal_width)
        return default_help_renderer(context, content)

    renderer = SchemaHelpRenderer(StandardLayout(), final_renderer=finalize)
    command = _command("x")
    schema = ParserSchema(
        raw_description=None,
        raw_epilog=None,
        commands={"demo": command},
        command_key=None,
        allow_args_from_file=False,
        pipe_targets=None,
    )

    freeze_terminal(monkeypatch, 50)
    narrow = renderer.render_parser_help(schema, "demo")
    freeze_terminal(monkeypatch, 100)
    wide = renderer.render_parser_help(schema, "demo")
    renderer.terminal_width = 72
    renderer.render_parser_help(schema, "demo")

    assert narrow != wide
    assert rendered_widths == [50, 100, 72]


def test_render_uses_custom_layout_subclass_overrides() -> None:
    class CustomAligned(Aligned):
        def format_argument(self, arg: Argument, indent: int = 2) -> str:
            return super().format_argument(arg, indent) + " <custom>"

    output = SchemaHelpRenderer(CustomAligned(), terminal_width=100).render_command_help(
        _command("x"), "demo"
    )

    assert "<custom>" in output


@pytest.mark.parametrize("fail_inner", [False, True])
def test_nested_render_restores_outer_measurements_and_uses_configured_layout(
    fail_inner: bool,
) -> None:
    layout = Aligned(default_field_width_max=None)
    outer = _command("a long default")
    inner = _command("x")
    nested_output: list[str] = []

    def finalize(context: HelpContext, content: HelpContent) -> str:
        if context.prog == "inner" and fail_inner:
            raise ValueError("Nested renderer failed")

        if context.prog == "outer":
            if fail_inner:
                with pytest.raises(ValueError, match="Nested renderer failed"):
                    renderer.render_command_help(inner, "inner")
            else:
                nested_output.append(renderer.render_command_help(inner, "inner"))

        return default_help_renderer(context, content)

    renderer = SchemaHelpRenderer(layout, terminal_width=120, final_renderer=finalize)
    outer_output = renderer.render_command_help(outer, "outer")

    if not fail_inner:
        assert nested_output == [
            SchemaHelpRenderer(layout, terminal_width=120).render_command_help(inner, "inner")
        ]

    assert outer_output == SchemaHelpRenderer(layout, terminal_width=120).render_command_help(
        outer, "outer"
    )


def test_failed_layout_override_restores_renderer_and_configured_measurements() -> None:
    should_raise = True

    class FailingAligned(Aligned):
        def format_argument(self, arg: Argument, indent: int = 2) -> str:
            if should_raise and arg.name == "value":
                raise ValueError("Cannot render this argument")

            return super().format_argument(arg, indent)

    layout = FailingAligned(default_field_width_max=None)
    renderer = SchemaHelpRenderer(layout, terminal_width=120)
    command = _command("a long default")

    with pytest.raises(ValueError, match="Cannot render this argument"):
        renderer.render_command_help(command, "demo")

    should_raise = False
    assert renderer.render_command_help(command, "demo") == SchemaHelpRenderer(
        layout, terminal_width=120
    ).render_command_help(command, "demo")


def test_adaptive_row_continuations_reserve_outer_indent() -> None:
    command = Command(
        obj=None,
        canonical_name="serve",
        cli_name="serve",
        aliases=(),
        raw_description=None,
        executable_flags=[
            ExecutableFlag(
                ("-d", "--disable-job-duration-limit"),
                lambda: None,
                help="Disable the per-job duration limit.",
            )
        ],
    )
    output = strip_ansi(
        SchemaHelpRenderer(StandardLayout(), terminal_width=50).render_command_help(
            command, "serve"
        )
    )
    lines = output.splitlines()
    row_index = next(index for index, line in enumerate(lines) if line.lstrip().startswith("-d,"))
    description_column = lines[row_index].index("Disable")
    continuation = lines[row_index + 1 :]

    assert continuation
    assert all(len(line) - len(line.lstrip()) == description_column for line in continuation)
    assert " ".join(
        [lines[row_index][description_column:], *(line.strip() for line in continuation)]
    ) == ("Disable the per-job duration limit.")
    assert all(len(line) <= 50 for line in lines)

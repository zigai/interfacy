from __future__ import annotations

import argparse
import inspect
import os
import re
from dataclasses import dataclass
from typing import Literal

import pytest
from stdl.st import TextStyle

from interfacy import CommandGroup, ExecutableFlag, Interfacy
from interfacy.argparse_backend.argument_parser import ArgumentParser
from interfacy.exceptions import UsageError
from interfacy.help.colors import NoColor
from interfacy.help.presets import (
    Aligned,
    AlignedTyped,
    ArgparseLayout,
    InterfacyLayout,
    Modern,
    StandardLayout,
)
from interfacy.help.terminal import strip_ansi
from interfacy.schema.schema import Command, ParserSchema


@dataclass
class ExpandableSettings:
    enabled: bool = False


DEFAULT_EXPANDABLE_SETTINGS = ExpandableSettings()


def run_with_expandable_settings(
    settings: ExpandableSettings = DEFAULT_EXPANDABLE_SETTINGS,
) -> None:
    return None


def test_layout_constructor_accepts_inline_kwargs() -> None:
    layout = ArgparseLayout(clear_metavar=True, help_position=44, help_option_description="Help.")
    assert layout.clear_metavar is True
    assert layout.help_position == 44
    assert layout.help_option_description == "Help."


def test_color_theme_constructor_accepts_inline_kwargs() -> None:
    theme = NoColor(flag_short=TextStyle(color="red"), description=TextStyle(color="yellow"))
    assert theme.flag_short.color == "red"
    assert theme.description.color == "yellow"


def test_layout_constructor_signature_exposes_supported_settings() -> None:
    signature = inspect.signature(ArgparseLayout)
    assert "clear_metavar" in signature.parameters
    assert "help_position" in signature.parameters
    assert signature.parameters["clear_metavar"].kind == inspect.Parameter.KEYWORD_ONLY


def test_standard_layout_hides_option_metavar_by_default() -> None:
    def demo(*, level: int = 2) -> None:
        return None

    parser = Interfacy(backend="argparse", help_layout=StandardLayout(), print_result=False)
    parser.add_command(demo)
    help_text = parser.build_parser().format_help()

    assert "-l, --level LEVEL" not in help_text
    assert "--level" in help_text


def test_standard_layout_does_not_leave_blank_metavar_slots_in_usage() -> None:
    def demo(*, count: int = 1, delay: float = 0.5) -> None:
        return None

    parser = Interfacy(backend="argparse", help_layout=StandardLayout(), print_result=False)
    parser.add_command(demo)
    built_parser = parser.build_parser()
    built_parser.prog = "demo"
    help_text = built_parser.format_help()
    usage_block = help_text.split("\n\n", 1)[0]

    assert "[-c ]" not in usage_block
    assert "[-d ]" not in usage_block
    assert "[-c]" in usage_block
    assert "[-d]" in usage_block


def test_standard_layout_renders_defaults_with_bracket_default_block() -> None:
    def demo(*, level: int = 2) -> None:
        """Set output level."""
        return None

    parser = Interfacy(backend="argparse", help_layout=StandardLayout(), print_result=False)
    parser.add_command(demo)
    help_text = parser.build_parser().format_help()
    level_line = next(line for line in help_text.splitlines() if "--level" in line)

    assert "[default: 2]" in level_line
    assert "Defaults to 2." not in level_line


def test_standard_layout_does_not_duplicate_existing_bracket_default_block() -> None:
    def demo(*, level: int = 2) -> None:
        """Set output level [default: 2]."""
        return None

    parser = Interfacy(backend="argparse", help_layout=StandardLayout(), print_result=False)
    parser.add_command(demo)
    help_text = parser.build_parser().format_help()
    level_line = next(line for line in help_text.splitlines() if "--level" in line)

    assert level_line.count("[default: 2]") == 1


def test_color_theme_constructor_signature_exposes_supported_settings() -> None:
    signature = inspect.signature(NoColor)
    assert "flag_short" in signature.parameters
    assert "description" in signature.parameters
    assert signature.parameters["flag_short"].kind == inspect.Parameter.KEYWORD_ONLY


def test_layout_constructor_rejects_unknown_setting_kwargs() -> None:
    with pytest.raises(TypeError, match="unexpected keyword argument 'unknown_layout_setting'"):
        ArgparseLayout(unknown_layout_setting=True)


def test_argparse_layout_root_usage_includes_subcommand_choices() -> None:
    def dense_parameters() -> None:
        """Exercise choices, defaults, tuples, and long descriptions."""

    def path_ops() -> None:
        """Mix positionals, varargs, and keyword-only options."""

    parser = Interfacy(backend="argparse", help_layout=ArgparseLayout(), print_result=False)
    parser.add_command(dense_parameters)
    parser.add_command(path_ops)

    help_text = parser.build_parser().format_help()
    assert "{dense-parameters,path-ops}" in help_text


def test_argparse_layout_uses_primary_boolean_option_form() -> None:
    def run(flag: bool = False) -> None:
        """No-op."""

    parser = Interfacy(backend="argparse", help_layout=ArgparseLayout(), print_result=False)
    parser.add_command(run)

    help_text = parser.build_parser().format_help()
    assert "--flag" in help_text
    assert "--no-flag" not in help_text


def test_argparse_layout_usage_uses_single_primary_boolean_form() -> None:
    def run(*, dry_run: bool = False) -> None:
        """No-op."""

    parser = Interfacy(backend="argparse", help_layout=ArgparseLayout(), print_result=False)
    parser.add_command(run)

    help_text = parser.build_parser().format_help()
    assert "[--dry-run]" in help_text
    assert "| --dry-run" not in help_text


def test_argparse_layout_shows_subcommand_description_rows() -> None:
    def run_fast() -> None:
        """Fast mode."""

    def run_safe() -> None:
        """Safe mode."""

    parser = Interfacy(backend="argparse", help_layout=ArgparseLayout(), print_result=False)
    parser.add_command(run_fast)
    parser.add_command(run_safe)

    help_text = parser.build_parser().format_help()
    assert "run-fast" in help_text
    assert "Fast mode." in help_text
    assert "run-safe" in help_text
    assert "Safe mode." in help_text


def test_argparse_layout_root_uses_commands_section_without_choices_header_line() -> None:
    def dense_parameters() -> None:
        """Dense command."""

    def path_ops() -> None:
        """Path command."""

    parser = Interfacy(backend="argparse", help_layout=ArgparseLayout(), print_result=False)
    parser.add_command(dense_parameters)
    parser.add_command(path_ops)

    help_text = parser.build_parser().format_help()
    assert "commands:" in help_text
    assert "positional arguments:" not in help_text
    assert "\ncommands:\n  {dense-parameters,path-ops}" not in help_text
    assert re.search(r"^\s*dense-parameters\s+Dense command\.$", help_text, re.MULTILINE)
    assert re.search(r"^\s*path-ops\s+Path command\.$", help_text, re.MULTILINE)


def test_nested_manual_parser_uses_leaf_metavar_for_append_action() -> None:
    parser = ArgumentParser(prog="manual")
    subparsers = parser.add_subparsers(dest="command", required=True)
    deploy = subparsers.add_parser("deploy")
    deploy.add_argument("--tag", action="append", default=None, help="Attach a tag.")

    help_text = deploy.format_help()
    assert "--tag TAG" in help_text
    assert "DEPLOY__TAG" not in help_text


def test_argument_parser_defaults_to_standard_layout() -> None:
    parser = ArgumentParser(prog="manual")
    assert isinstance(parser._interfacy_help_layout, StandardLayout)


def test_argument_parser_disables_argparse_usage_colors_when_python_colors_forced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTHON_COLORS", "1")
    parser = ArgumentParser(prog="agentctl pi")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("new", "send", "skill", "slash", "steer", "rename"):
        subparsers.add_parser(name)

    with pytest.raises(UsageError) as excinfo:
        parser.parse_args(["status"])
    assert "invalid choice: 'status'" in str(excinfo.value)
    assert excinfo.value.usage == strip_ansi(excinfo.value.usage or "")


def test_manual_argument_parser_help_position_keeps_long_option_description_inline() -> None:
    parser = ArgumentParser(prog="manual", help_position=42)
    parser.add_argument(
        "-d",
        "--disable-job-duration-limit",
        action="store_true",
        help="Disable the per-job duration limit.",
    )

    help_text = parser.format_help()

    assert re.search(
        r"^\s*-d, --disable-job-duration-limit\s+Disable the per-job duration limit\.$",
        help_text,
        re.MULTILINE,
    )


def test_argparser_help_position_kwarg_overrides_layout_help_position() -> None:
    parser = Interfacy(
        backend="argparse",
        help_layout=StandardLayout(help_position=24),
        help_position=42,
        executable_flags=[
            ExecutableFlag(
                ("-d", "--disable-job-duration-limit"),
                lambda: None,
                help="Disable the per-job duration limit.",
            )
        ],
        print_result=False,
    )

    def serve() -> None:
        """Run the service."""

    parser.add_command(serve)
    help_text = parser.build_parser().format_help()

    assert re.search(
        r"^\s*-d, --disable-job-duration-limit\s+Disable the per-job duration limit\.$",
        help_text,
        re.MULTILINE,
    )


def test_manual_modern_layout_renders_template_details_without_attached_schema() -> None:
    parser = ArgumentParser(
        prog="deploy",
        description="Deploy an application build.",
        help_layout=Modern(),
    )
    parser.add_argument(
        "environment",
        choices=("staging", "production"),
        help="Target environment.",
    )
    parser.add_argument("--region", default="us-east-1", help="Cloud region.")
    parser.add_argument(
        "--strategy",
        choices=("rolling", "blue-green", "canary"),
        default="rolling",
        help="Deployment strategy.",
    )
    parser.add_argument(
        "--color",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable color output.",
    )

    help_text = re.sub(r"\x1b\[[0-9;]*m", "", parser.format_help())

    assert "↳ choices: staging, production" in help_text
    assert "↳ default: us-east-1 | type: str" in help_text
    assert "↳ default: rolling | choices: rolling, blue-green," in help_text
    assert "canary" in help_text
    assert "--no-color" in help_text
    assert "↳ default: true" in help_text


def test_manual_modern_layout_lists_subcommands_without_attached_schema() -> None:
    parser = ArgumentParser(
        prog="manual",
        description="Manual CLI.",
        help_layout=Modern(),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("clone", help="Clone a repository.")
    subparsers.add_parser("status", help="Show current status.")

    help_text = re.sub(r"\x1b\[[0-9;]*m", "", parser.format_help())

    assert "{clone,status}" in help_text
    assert re.search(r"^\s*clone\s+Clone a repository\.$", help_text, re.MULTILINE)
    assert re.search(r"^\s*status\s+Show current status\.$", help_text, re.MULTILINE)


def test_group_function_commands_render_kebab_case_names() -> None:
    ops = CommandGroup("ops")

    def cache_prune() -> None:
        """Prune cache keys."""

    ops.add_command(cache_prune)
    parser = Interfacy(backend="argparse", help_layout=ArgparseLayout(), print_result=False)
    parser.add_command(ops)

    root = parser.build_parser()
    action = next(a for a in root._actions if isinstance(a, argparse._SubParsersAction))
    ops_parser = action.choices["ops"]
    help_text = ops_parser.format_help()

    assert "cache-prune" in help_text
    assert "cache_prune" not in help_text


def test_grouped_root_help_omits_help_option_when_add_help_disabled() -> None:
    layout = ArgparseLayout()
    parser = ArgumentParser(prog="manual", help_layout=layout, add_help=False)
    parser.set_schema(
        ParserSchema(
            raw_description=None,
            raw_epilog=None,
            commands={
                "clone": Command(
                    obj=None,
                    canonical_name="clone",
                    cli_name="clone",
                    aliases=(),
                    raw_description="Clone a repository.",
                    help_group="setup",
                ),
                "status": Command(
                    obj=None,
                    canonical_name="status",
                    cli_name="status",
                    aliases=(),
                    raw_description="Show current status.",
                ),
            },
            command_key=None,
            allow_args_from_file=False,
            pipe_targets=None,
        )
    )

    help_text = parser.format_help()

    assert "--help" not in help_text
    assert "options:" not in help_text


def test_grouped_subcommand_help_preserves_custom_help_flag_prefix() -> None:
    layout = ArgparseLayout()
    parser = ArgumentParser(prog="manual ops", help_layout=layout, prefix_chars="+")
    parser.set_schema_command(
        Command(
            obj=None,
            canonical_name="ops",
            cli_name="ops",
            aliases=(),
            raw_description="Operations.",
            subcommands={
                "clone": Command(
                    obj=None,
                    canonical_name="clone",
                    cli_name="clone",
                    aliases=(),
                    raw_description="Clone a repository.",
                    help_group="setup",
                ),
                "status": Command(
                    obj=None,
                    canonical_name="status",
                    cli_name="status",
                    aliases=(),
                    raw_description="Show current status.",
                ),
            },
            is_leaf=False,
        )
    )

    help_text = parser.format_help()

    assert "[++help]" in help_text
    assert "  ++help" in help_text
    assert "--help" not in help_text


def test_interfacy_layout_usage_lists_concrete_subcommand_choices() -> None:
    class Math:
        def add(self) -> None:
            return None

        def mul(self) -> None:
            return None

    parser = Interfacy(backend="argparse", help_layout=InterfacyLayout(), print_result=False)
    parser.add_command(Math)

    help_text = parser.build_parser().format_help()
    assert "{add,mul}" in help_text


def test_standard_layout_class_root_help_renders_one_commands_section() -> None:
    class Calculator:
        def add(self, a: float, b: float) -> float:
            return a + b

        def mul(self, a: float, b: float) -> float:
            return a * b

    parser = Interfacy(backend="argparse", help_layout=StandardLayout(), print_result=False)
    parser.add_command(Calculator)

    help_text = parser.build_parser().format_help()

    assert len(re.findall(r"^commands:$", help_text, re.MULTILINE)) == 1
    assert len(re.findall(r"^\s+add(?:\s|$)", help_text, re.MULTILINE)) == 1
    assert len(re.findall(r"^\s+mul(?:\s|$)", help_text, re.MULTILINE)) == 1


def test_interfacy_layout_usage_subcommand_choices_exclude_aliases() -> None:
    ops = CommandGroup("ops")
    ops.add_command(lambda: None, name="cache_prune", aliases=("prune",))

    parser = Interfacy(backend="argparse", help_layout=InterfacyLayout(), print_result=False)
    parser.add_command(ops)

    root = parser.build_parser()
    action = next(a for a in root._actions if isinstance(a, argparse._SubParsersAction))
    ops_parser = action.choices["ops"]
    help_text = ops_parser.format_help()

    assert "{cache-prune}" in help_text
    assert "{cache-prune,prune}" not in help_text


def test_interfacy_layout_help_and_choices_metadata_align_in_same_column() -> None:
    def dense_parameters(
        input_path: str,
        output_path: str,
        *,
        mode: Literal["fast", "safe", "balanced"] = "balanced",
    ) -> None:
        return None

    parser = Interfacy(backend="argparse", help_layout=InterfacyLayout(), print_result=False)
    parser.add_command(dense_parameters)

    help_text = parser.build_parser().format_help()
    help_line = next(
        line for line in help_text.splitlines() if "--help" in line and "Show " in line
    )
    mode_line = next(
        line for line in help_text.splitlines() if "--mode" in line and "[choices:" in line
    )
    assert help_line.index("Show") == mode_line.index("[choices:")


def test_interfacy_layout_help_and_type_metadata_align_in_same_column() -> None:
    def path_ops(source: str, target: str, *extras: str, level: int = 2) -> None:
        return None

    parser = Interfacy(backend="argparse", help_layout=InterfacyLayout(), print_result=False)
    parser.add_command(path_ops)

    help_text = parser.build_parser().format_help()
    help_line = next(
        line for line in help_text.splitlines() if "--help" in line and "Show " in line
    )
    level_line = next(
        line for line in help_text.splitlines() if "--level" in line and "[default=" in line
    )
    assert help_line.index("Show") == level_line.index("[default=")


def test_interfacy_layout_displays_empty_string_defaults_explicitly() -> None:
    def db_tool(*, db_path: str = "") -> None:
        """SQLite database path. Use the configured default when empty."""
        return None

    parser = Interfacy(backend="argparse", help_layout=InterfacyLayout(), print_result=False)
    parser.add_command(db_tool)

    help_text = re.sub(r"\x1b\[[0-9;]*m", "", parser.build_parser().format_help())
    db_line = next(
        line for line in help_text.splitlines() if "--db-path" in line and "[default=" in line
    )

    assert '[default="", type: str]' in db_line


def test_interfacy_layout_does_not_add_extra_leading_space_for_ansi_only_description() -> None:
    layout = InterfacyLayout()
    values = {
        "description": "\x1b[38;5;15m\x1b[0m",
        "extra": "[default=3, type: int]",
    }
    applied = layout._apply_interfacy_columns(values)
    assert applied["extra"] == "[default=3, type: int]"


def test_aligned_layout_help_only_option_row_is_not_over_indented() -> None:
    def dense_parameters() -> None:
        """Dense command."""

    def path_ops() -> None:
        """Path command."""

    parser = Interfacy(backend="argparse", help_layout=Aligned(), print_result=False)
    parser.add_command(dense_parameters)
    parser.add_command(path_ops)

    help_text = parser.build_parser().format_help()
    help_line = next(
        line for line in help_text.splitlines() if "--help" in line and "Show " in line
    )
    assert help_line.startswith("  --help")
    assert not help_line.startswith("        --help")


@pytest.mark.parametrize("layout_cls", [Aligned, AlignedTyped])
def test_aligned_family_help_option_continuation_aligns_to_description_column(
    layout_cls: type[Aligned | AlignedTyped],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "shutil.get_terminal_size",
        lambda *args, **kwargs: os.terminal_size((60, 24)),
    )
    monkeypatch.setattr(
        "os.get_terminal_size",
        lambda *args, **kwargs: os.terminal_size((60, 24)),
    )

    def demo(*, delay: float = 0.5) -> None:
        return None

    parser = Interfacy(backend="argparse", help_layout=layout_cls(), print_result=False)
    parser.add_command(demo)
    help_text = re.sub(r"\x1b\[[0-9;]*m", "", parser.build_parser().format_help())
    lines = help_text.splitlines()
    first = next(line for line in lines if "--help" in line and "Show" in line)
    second = next(line for line in lines if "message and exit" in line)

    assert first.index("Show") == second.index("message")


@pytest.mark.parametrize("layout_cls", [Aligned, AlignedTyped])
def test_aligned_family_choice_continuation_uses_metadata_column(
    layout_cls: type[Aligned | AlignedTyped],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "shutil.get_terminal_size",
        lambda *args, **kwargs: os.terminal_size((60, 24)),
    )
    monkeypatch.setattr(
        "os.get_terminal_size",
        lambda *args, **kwargs: os.terminal_size((60, 24)),
    )

    def demo(*, mode: Literal["fast", "safe", "balanced"] = "balanced") -> None:
        return None

    parser = Interfacy(backend="argparse", help_layout=layout_cls(), print_result=False)
    parser.add_command(demo)
    help_text = re.sub(r"\x1b\[[0-9;]*m", "", parser.build_parser().format_help())
    lines = help_text.splitlines()
    first = next(line for line in lines if "--mode" in line and "[choices:" in line)
    second = next(line for line in lines if "balanced]" in line and "--mode" not in line)

    assert second.index("balanced]") >= first.index("[choices:")


def test_aligned_typed_positional_literal_choices_keep_column_padding() -> None:
    def demo(target: Literal["dev", "prod"]) -> None:
        return None

    parser = Interfacy(backend="argparse", help_layout=AlignedTyped(), print_result=False)
    parser.add_command(demo)
    help_text = re.sub(r"\x1b\[[0-9;]*m", "", parser.build_parser().format_help())
    target_line = next(
        line for line in help_text.splitlines() if "TARGET" in line and "[choices:" in line
    )

    assert "TARGET [choices:" not in target_line
    assert "TARGET                   [choices: dev, prod]" in target_line


@pytest.mark.parametrize("layout_cls", [Aligned, AlignedTyped])
def test_aligned_family_help_only_option_continuation_aligns(
    layout_cls: type[Aligned | AlignedTyped],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "shutil.get_terminal_size",
        lambda *args, **kwargs: os.terminal_size((60, 24)),
    )
    monkeypatch.setattr(
        "os.get_terminal_size",
        lambda *args, **kwargs: os.terminal_size((60, 24)),
    )

    def demo() -> None:
        return None

    parser = Interfacy(backend="argparse", help_layout=layout_cls(), print_result=False)
    parser.add_command(demo)
    help_text = re.sub(r"\x1b\[[0-9;]*m", "", parser.build_parser().format_help())
    lines = help_text.splitlines()
    first = next(line for line in lines if "--help" in line and "Show" in line)
    second = next(line for line in lines if "message and exit" in line)

    assert first.index("Show") == second.index("message")


def test_modern_detail_continuation_uses_detail_column(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "shutil.get_terminal_size",
        lambda *args, **kwargs: os.terminal_size((60, 24)),
    )
    monkeypatch.setattr(
        "os.get_terminal_size",
        lambda *args, **kwargs: os.terminal_size((60, 24)),
    )

    def demo(*, mode: Literal["fast", "safe", "balanced"] = "balanced") -> None:
        return None

    parser = Interfacy(backend="argparse", help_layout=Modern(), print_result=False)
    parser.add_command(demo)
    help_text = re.sub(r"\x1b\[[0-9;]*m", "", parser.build_parser().format_help())
    lines = help_text.splitlines()
    first = next(line for line in lines if "--mode" in line and "choices:" in line)
    second = next(line for line in lines if "fast, safe, balanced" in line)

    assert first.index("→") == second.index("fast")


@pytest.mark.parametrize("layout_cls", [Aligned, AlignedTyped])
def test_aligned_family_omits_suppressed_boolean_default_for_model_expansion(
    layout_cls: type[Aligned | AlignedTyped],
) -> None:
    parser = Interfacy(backend="argparse", help_layout=layout_cls(), print_result=False)
    parser.add_command(run_with_expandable_settings)
    help_text = re.sub(r"\x1b\[[0-9;]*m", "", parser.build_parser().format_help())
    assert re.search(r"--settings[._-]?enabled", help_text)
    assert re.search(r"--settings[._-]?enabled\s+enabled", help_text)
    assert "true" not in help_text.lower()


def test_aligned_typed_help_aligns_to_metadata_column_when_options_are_metadata_only() -> None:
    def ytmp3_like(
        *urls: str,
        album: str | None = None,
        output: str = "%(title)s.%(ext)s",
        quiet: bool = False,
    ) -> None:
        return None

    parser = Interfacy(backend="argparse", help_layout=AlignedTyped(), print_result=False)
    parser.add_command(ytmp3_like)
    help_text = re.sub(r"\x1b\[[0-9;]*m", "", parser.build_parser().format_help())

    lines = help_text.splitlines()
    help_line = next(
        line for line in lines if "--help" in line and "Show this help message and exit" in line
    )
    album_line = next(line for line in lines if "--album" in line and "[type:" in line)
    output_line = next(
        line for line in lines if "--output" in line and "[%(title)s.%(ext)s]" in line
    )

    help_idx = help_line.index("Show this help message and exit")
    assert help_idx == album_line.index("[type:")
    assert help_idx == output_line.index("[")


@pytest.mark.parametrize("layout_cls", [Aligned, AlignedTyped])
def test_aligned_family_hides_false_default_for_positive_boolean_flags(
    layout_cls: type[Aligned | AlignedTyped],
) -> None:
    def pull_all_like(*, quiet: bool = False) -> None:
        return None

    parser = Interfacy(backend="argparse", help_layout=layout_cls(), print_result=False)
    parser.add_command(pull_all_like)
    help_text = re.sub(r"\x1b\[[0-9;]*m", "", parser.build_parser().format_help())

    quiet_line = next(
        line
        for line in help_text.splitlines()
        if line.lstrip().startswith("-") and "--quiet" in line
    )
    assert "[" not in quiet_line


@pytest.mark.parametrize("layout_cls", [Aligned, AlignedTyped])
def test_aligned_family_keeps_true_default_for_negative_boolean_flags(
    layout_cls: type[Aligned | AlignedTyped],
) -> None:
    def compress_like(*, recursive: bool = True) -> None:
        return None

    parser = Interfacy(backend="argparse", help_layout=layout_cls(), print_result=False)
    parser.add_command(compress_like)
    help_text = re.sub(r"\x1b\[[0-9;]*m", "", parser.build_parser().format_help())

    recursive_line = next(
        line
        for line in help_text.splitlines()
        if line.lstrip().startswith("-") and "--no-recursive" in line
    )
    assert "true" in recursive_line.lower()


def test_usage_metavars_use_kebab_case_for_nested_class_commands() -> None:
    class ReportTool:
        def __init__(self, output_dir: str) -> None:
            self.output_dir = output_dir

        def compare(self, left: str, right: str) -> None:
            return None

    parser = Interfacy(backend="argparse", help_layout=InterfacyLayout(), print_result=False)
    parser.add_command(ReportTool)
    root = parser.build_parser()
    action = next(a for a in root._actions if isinstance(a, argparse._SubParsersAction))
    compare_parser = action.choices["compare"]
    help_text = compare_parser.format_help()

    assert "OUTPUT-DIR" in help_text
    assert "OUTPUT_DIR" not in help_text


def test_argparse_layout_group_usage_includes_subcommand_choices() -> None:
    ops = CommandGroup("ops")
    ops.add_command(lambda: None, name="cache_prune")

    parser = Interfacy(backend="argparse", help_layout=ArgparseLayout(), print_result=False)
    parser.add_command(ops)
    root = parser.build_parser()
    action = next(a for a in root._actions if isinstance(a, argparse._SubParsersAction))
    ops_parser = action.choices["ops"]
    help_text = ops_parser.format_help()

    assert "{cache-prune}" in help_text

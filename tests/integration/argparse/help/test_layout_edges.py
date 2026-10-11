from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from enum import Enum

import pytest

from interfacy import BooleanMode, Interfacy
from interfacy.common.terminal import strip_ansi
from interfacy.help import (
    Aligned,
    AlignedTyped,
    ArgparseLayout,
    HelpLayout,
    InterfacyLayout,
)
from interfacy.schema.nodes import (
    Argument,
    ArgumentDefault,
    ArgumentKind,
    BooleanBehavior,
    ValueShape,
)
from interfacy.schema.values import ValueCardinality
from tests.fixtures.terminal import freeze_terminal


def make_argument(
    *,
    name: str,
    flags: tuple[str, ...],
    kind: ArgumentKind = ArgumentKind.OPTION,
    value_shape: ValueShape = ValueShape.SINGLE,
    required: bool = False,
    default: object = None,
    help_text: str | None = None,
    type_: type | None = str,
    choices: tuple[object, ...] | None = None,
    boolean_behavior: BooleanBehavior | None = None,
    is_help_action: bool = False,
) -> Argument:
    if value_shape is ValueShape.FLAG:
        cardinality = ValueCardinality(0, 0, 0)
    else:
        cardinality = ValueCardinality(1 if required else 0, 1, 1)

    return Argument(
        name=name,
        display_name=name,
        kind=kind,
        value_shape=value_shape,
        flags=flags,
        required=required,
        cardinality=cardinality,
        argument_default=ArgumentDefault.present(default),
        help=help_text,
        type=type_,
        parser=None,
        choices=choices,
        boolean_behavior=boolean_behavior,
        is_help_action=is_help_action,
    )


def test_schema_argument_legacy_required_untyped_positional_has_no_help() -> None:
    layout = HelpLayout(format_positional=None, format_option=None)
    arg = make_argument(
        name="path",
        flags=("path",),
        kind=ArgumentKind.POSITIONAL,
        required=True,
        type_=None,
        help_text="Path value.",
    )

    assert layout.format_argument(arg) == ""


def test_schema_argument_legacy_bool_adds_sentence_punctuation() -> None:
    layout = HelpLayout(format_positional=None, format_option=None)
    arg = make_argument(
        name="verbose",
        flags=("--verbose",),
        value_shape=ValueShape.FLAG,
        default=False,
        help_text="Enable verbose mode",
        type_=None,
        boolean_behavior=BooleanBehavior(
            positive_flags=("--verbose",),
            negative_flags=("--no-verbose",),
            default=False,
            mode=BooleanMode.DUAL,
        ),
    )

    assert strip_ansi(layout.format_argument(arg)).endswith("Enable verbose mode.")


def test_schema_argument_choices_with_default_render_once() -> None:
    layout = InterfacyLayout()
    arg = make_argument(
        name="mode",
        flags=("--mode",),
        required=False,
        default="safe",
        help_text="Execution mode.",
        type_=str,
        choices=("fast", "safe"),
    )

    rendered = strip_ansi(layout.format_argument(arg))

    assert "choices:" in rendered
    assert "fast, safe" in rendered
    assert rendered.count("default=safe") == 1


class Color(Enum):
    RED = "red"
    BLUE = "blue"


def test_schema_argument_enum_choice_uses_value_for_argparse_layout() -> None:
    layout = ArgparseLayout()
    arg = make_argument(
        name="color",
        flags=("--color",),
        default=Color.RED,
        type_=Color,
        choices=(Color.RED, Color.BLUE),
    )

    rendered = strip_ansi(layout.format_argument(arg))

    assert "red" in rendered
    assert "blue" in rendered
    assert "Color.RED" not in rendered


def test_schema_help_action_suppresses_bool_default() -> None:
    layout = InterfacyLayout()
    arg = make_argument(
        name="help",
        flags=("-h", "--help"),
        value_shape=ValueShape.FLAG,
        default=argparse.SUPPRESS,
        help_text="Show help.",
        type_=None,
        boolean_behavior=BooleanBehavior(
            positive_flags=("-h", "--help"),
            negative_flags=(),
            default=argparse.SUPPRESS,
            mode=BooleanMode.POSITIVE_ONLY,
        ),
        is_help_action=True,
    )

    rendered = strip_ansi(layout.format_argument(arg))

    assert "Show help." in rendered
    assert "default" not in rendered


@pytest.mark.parametrize(("layout_cls", "show_type"), [(Aligned, False), (AlignedTyped, True)])
def test_aligned_presets_keep_template_and_constructor_customization(
    layout_cls: type[Aligned | AlignedTyped],
    show_type: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    freeze_terminal(monkeypatch, 120)
    layout = layout_cls(short_flag_width=8, long_flag_width=20, default_field_width=9)
    argument = make_argument(
        name="count",
        flags=("-c", "--count"),
        type_=int,
        default=2,
        help_text="Number of items.",
    )

    rendered = strip_ansi(layout.format_argument(argument))

    assert rendered.startswith(f"{'-c':<8}{'--count':<20}[{'2':>9}] Number of items.")
    assert ("[type: int]" in rendered) is show_type


@dataclass
class ExpandableSettings:
    enabled: bool = False


DEFAULT_EXPANDABLE_SETTINGS = ExpandableSettings()


def run_with_expandable_settings(
    settings: ExpandableSettings = DEFAULT_EXPANDABLE_SETTINGS,
) -> None:
    return None


def test_layout_constructor_rejects_unknown_setting_kwargs() -> None:
    with pytest.raises(TypeError, match="unexpected keyword argument 'unknown_layout_setting'"):
        ArgparseLayout(unknown_layout_setting=True)


def test_interfacy_layout_does_not_add_extra_leading_space_for_ansi_only_description() -> None:
    layout = InterfacyLayout()
    values = {
        "description": "\x1b[38;5;15m\x1b[0m",
        "extra": "[default=3, type: int]",
    }
    applied = layout._apply_interfacy_columns(values)
    assert applied["extra"] == "[default=3, type: int]"


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

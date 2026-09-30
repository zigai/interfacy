from __future__ import annotations

import argparse
from enum import Enum

import pytest

from interfacy import BooleanMode
from interfacy.common.terminal import strip_ansi
from interfacy.help import (
    Aligned,
    AlignedTyped,
    ArgparseLayout,
    HelpLayout,
    InterfacyLayout,
)
from interfacy.schema.model import (
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

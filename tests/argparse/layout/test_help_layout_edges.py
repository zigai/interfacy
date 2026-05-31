from __future__ import annotations

import argparse
import os
from enum import Enum

from interfacy.appearance.layouts import ArgparseLayout, HelpLayout, InterfacyLayout
from interfacy.schema.schema import Argument, ArgumentKind, BooleanBehavior, ValueShape
from interfacy.util import strip_ansi


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
    return Argument(
        name=name,
        display_name=name,
        kind=kind,
        value_shape=value_shape,
        flags=flags,
        required=required,
        default=default,
        help=help_text,
        type=type_,
        parser=None,
        choices=choices,
        boolean_behavior=boolean_behavior,
        is_help_action=is_help_action,
    )


def test_default_field_width_uses_base_for_empty_lengths() -> None:
    layout = HelpLayout(default_field_width=18)

    assert layout._compute_default_field_width_from_lengths([]) == 18
    assert layout._compute_default_field_width_for_len(0) == 18


def test_default_field_width_clamps_to_terminal_and_configured_max(monkeypatch) -> None:
    layout = HelpLayout(
        pos_flag_width=12,
        default_field_width_term_ratio=2,
        default_field_width_soft_ratio=2,
        default_field_width_max=20,
    )
    monkeypatch.setattr(
        os, "get_terminal_size", lambda *args, **kwargs: os.terminal_size((100, 24))
    )

    assert layout._compute_default_field_width_for_len(80) == 20
    assert layout._compute_default_field_width_from_lengths([80, 20, 16]) == 20


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
            supports_negative=True,
            negative_form="--no-verbose",
            default=False,
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
            supports_negative=False,
            negative_form=None,
            default=argparse.SUPPRESS,
        ),
        is_help_action=True,
    )

    rendered = strip_ansi(layout.format_argument(arg))

    assert "Show help." in rendered
    assert "default" not in rendered

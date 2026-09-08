from __future__ import annotations

import argparse
import os
from enum import Enum

import pytest
from stdl.st import TextStyle, ansi_len

from interfacy import BooleanMode
from interfacy.help.layout import InterfacyColors
from interfacy.help.presets import (
    Aligned,
    AlignedTyped,
    ArgparseLayout,
    ClapLayout,
    HelpLayout,
    InterfacyLayout,
)
from interfacy.help.terminal import strip_ansi
from interfacy.schema.schema import (
    Argument,
    ArgumentDefault,
    ArgumentKind,
    BooleanBehavior,
    ValueCardinality,
    ValueShape,
)


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
    monkeypatch.setattr(
        os, "get_terminal_size", lambda *args, **kwargs: os.terminal_size((120, 24))
    )
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
    assert not isinstance(layout, AlignedTyped if layout_cls is Aligned else Aligned)


@pytest.mark.parametrize("layout_cls", [HelpLayout, ClapLayout])
def test_flag_columns_preserve_ansi_styling_and_visible_padding(
    layout_cls: type[HelpLayout],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    codes = {"red": "31", "green": "32", "cyan": "36"}

    def styled(text: str, style: TextStyle) -> str:
        return f"\x1b[{codes[style.color]}m{text}\x1b[0m"

    monkeypatch.setattr("interfacy.help.layout.with_style", styled)
    monkeypatch.setattr("interfacy.help.presets.with_style", styled)
    layout = layout_cls(
        style=InterfacyColors(
            flag_short=TextStyle(color="red"),
            flag_long=TextStyle(color="green"),
            placeholder_style=TextStyle(color="cyan"),
        ),
        short_flag_width=4,
        long_flag_width=24,
        pos_flag_width=32,
    )

    columns = layout._build_styled_columns(
        "-r", "--region <REGION>", "-r, --region <REGION>", is_option=True
    )

    short = "\x1b[31m-r\x1b[0m"
    long = (
        "\x1b[32m--region\x1b[0m \x1b[36m<REGION>\x1b[0m"
        if layout_cls is ClapLayout
        else "\x1b[32m--region <REGION>\x1b[0m"
    )
    assert columns["flag_short_styled"] == short
    assert columns["flag_long_styled"] == long
    assert columns["flag_styled"] == f"{short}, {long}"
    assert columns["flag_short_col"] == f"{short}  "
    assert columns["flag_long_col"] == long + " " * 7
    assert ansi_len(columns["flag_col"]) == 32

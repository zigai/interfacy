from dataclasses import dataclass

from stdl.st import TextStyle

from interfacy.help.layout import InterfacyColors

WHITE_TEXT = TextStyle(color="white")


@dataclass(kw_only=True)
class NoColor(InterfacyColors):
    """Color theme that renders help output without accent colors."""

    type: TextStyle = WHITE_TEXT
    type_keyword: TextStyle = WHITE_TEXT
    type_bracket: TextStyle = WHITE_TEXT
    type_punctuation: TextStyle = WHITE_TEXT
    type_operator: TextStyle = WHITE_TEXT
    type_literal: TextStyle = WHITE_TEXT
    default: TextStyle = WHITE_TEXT
    description: TextStyle = WHITE_TEXT
    string: TextStyle = WHITE_TEXT
    extra_data: TextStyle = WHITE_TEXT

    flag_short: TextStyle = WHITE_TEXT
    flag_long: TextStyle = WHITE_TEXT
    flag_positional: TextStyle = WHITE_TEXT


@dataclass(kw_only=True)
class Aurora(InterfacyColors):
    """Color theme inspired by aurora palettes."""

    type: TextStyle = TextStyle(color="light_cyan")
    type_keyword: TextStyle = TextStyle(color="light_blue")
    type_bracket: TextStyle = TextStyle(color="white")
    type_punctuation: TextStyle = TextStyle(color="white")
    type_operator: TextStyle = TextStyle(color="white")
    type_literal: TextStyle = TextStyle(color="yellow")
    default: TextStyle = TextStyle(color="light_magenta")
    description: TextStyle = TextStyle(color="white")
    string: TextStyle = TextStyle(color="yellow")
    extra_data: TextStyle = TextStyle(color="gray")
    flag_short: TextStyle = TextStyle(color="light_cyan")
    flag_long: TextStyle = TextStyle(color="light_blue")
    flag_positional: TextStyle = TextStyle(color="light_cyan")


@dataclass(kw_only=True)
class ClapColors(InterfacyColors):
    """Colors that mimic clap's default styled output."""

    type: TextStyle = TextStyle(color="light_green")
    type_keyword: TextStyle = TextStyle(color="light_green")
    type_bracket: TextStyle = TextStyle(color="white")
    type_punctuation: TextStyle = TextStyle(color="white")
    type_operator: TextStyle = TextStyle(color="white")
    type_literal: TextStyle = TextStyle(color="cyan")
    default: TextStyle = TextStyle(color="cyan")
    description: TextStyle = TextStyle(color="white")
    string: TextStyle = TextStyle(color="cyan")
    extra_data: TextStyle = TextStyle(color="white")

    flag_short: TextStyle = TextStyle(color="cyan", style="bold")
    flag_long: TextStyle = TextStyle(color="cyan", style="bold")
    flag_positional: TextStyle = TextStyle(color="cyan", style="bold")
    usage_style: TextStyle | None = TextStyle(color="light_green", style="bold")
    usage_text_style: TextStyle | None = TextStyle(color="cyan", style="bold")
    section_heading_style: TextStyle | None = TextStyle(
        color="light_green",
        style="bold",
    )
    placeholder_style: TextStyle | None = TextStyle(color="cyan", style="bold")
    command_name_style: TextStyle | None = TextStyle(color="cyan", style="bold")


__all__ = [
    "WHITE_TEXT",
    "Aurora",
    "ClapColors",
    "InterfacyColors",
    "NoColor",
]

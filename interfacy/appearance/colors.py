from dataclasses import dataclass

from stdl.st import TextStyle

from interfacy.appearance.layout import InterfacyColors


@dataclass(kw_only=True)
class NoColor(InterfacyColors):
    type: TextStyle = TextStyle(color="white")
    type_keyword: TextStyle = TextStyle(color="white")
    type_bracket: TextStyle = TextStyle(color="white")
    type_punctuation: TextStyle = TextStyle(color="white")
    type_operator: TextStyle = TextStyle(color="white")
    type_literal: TextStyle = TextStyle(color="white")
    default: TextStyle = TextStyle(color="white")
    description: TextStyle = TextStyle(color="white")
    string: TextStyle = TextStyle(color="white")
    extra_data: TextStyle = TextStyle(color="white")

    flag_short: TextStyle = TextStyle(color="white")
    flag_long: TextStyle = TextStyle(color="white")
    flag_positional: TextStyle = TextStyle(color="white")


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


__all__ = [
    "Aurora",
    "ClapColors",
    "InterfacyColors",
    "NoColor",
]

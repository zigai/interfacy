from stdl.st import TextStyle

from interfacy.appearance.layout import InterfacyColors


class NoColor(InterfacyColors):
    type = TextStyle(color="white")
    default = TextStyle(color="white")
    description = TextStyle(color="white")
    string = TextStyle(color="white")
    extra_data = TextStyle(color="white")

    flag_short = TextStyle(color="white")
    flag_long = TextStyle(color="white")
    flag_positional = TextStyle(color="white")


class Aurora(InterfacyColors):
    type = TextStyle(color="light_cyan")
    default = TextStyle(color="light_magenta")
    description = TextStyle(color="white")
    string = TextStyle(color="yellow")
    extra_data = TextStyle(color="gray")

    flag_short = TextStyle(color="light_cyan")
    flag_long = TextStyle(color="light_blue")
    flag_positional = TextStyle(color="light_cyan")


class ClapColors(InterfacyColors):
    """Colors that mimic clap's default styled output."""

    type = TextStyle(color="green")
    default = TextStyle(color="cyan")
    description = TextStyle(color="white")
    string = TextStyle(color="cyan")
    extra_data = TextStyle(color="white")

    flag_short = TextStyle(color="cyan", style="bold")
    flag_long = TextStyle(color="cyan", style="bold")
    flag_positional = TextStyle(color="cyan", style="bold")


__all__ = [
    "InterfacyColors",
    "NoColor",
    "Aurora",
    "ClapColors",
]

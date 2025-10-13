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


__all__ = [
    "InterfacyColors",
    "NoColor",
    "Aurora",
]

from types import SimpleNamespace

from stdl.st import TextStyle

from interfacy.help import formatting as type_help
from interfacy.help.formatting import format_type_for_help
from interfacy.help.layout import InterfacyColors


def _marker(text: str, style: TextStyle) -> str:
    color = style.color
    return f"<{color}>{text}</{color}>"


def test_type_hint_brackets_default_to_white(monkeypatch) -> None:
    monkeypatch.setattr(type_help, "with_style", _marker)
    theme = InterfacyColors()

    rendered = format_type_for_help("list[str]", theme.type, theme=theme)

    assert rendered == "<green>list</green><white>[</white><green>str</green><white>]</white>"


def test_type_hint_uses_full_token_styles(monkeypatch) -> None:
    monkeypatch.setattr(type_help, "with_style", _marker)
    theme = SimpleNamespace(
        type=TextStyle(color="green"),
        type_keyword=TextStyle(color="magenta"),
        type_bracket=TextStyle(color="white"),
        type_punctuation=TextStyle(color="cyan"),
        type_operator=TextStyle(color="red"),
        type_literal=TextStyle(color="yellow"),
    )

    rendered = format_type_for_help(
        "dict[str, Literal['x', 1] | int]",
        theme.type,
        theme=theme,
    )

    assert rendered == (
        "<green>dict</green>"
        "<white>[</white>"
        "<green>str</green>"
        "<cyan>,</cyan> "
        "<magenta>Literal</magenta>"
        "<white>[</white>"
        "<yellow>'x'</yellow>"
        "<cyan>,</cyan> "
        "<yellow>1</yellow>"
        "<white>]</white> "
        "<red>|</red> "
        "<green>int</green>"
        "<white>]</white>"
    )


def test_optional_suffix_uses_operator_style(monkeypatch) -> None:
    monkeypatch.setattr(type_help, "with_style", _marker)
    theme = InterfacyColors()
    theme.type_operator = TextStyle(color="red")

    rendered = format_type_for_help(list[str] | None, theme.type, theme=theme)

    assert (
        rendered
        == "<green>list</green><white>[</white><green>str</green><white>]</white><red>?</red>"
    )


def test_format_type_for_help_uses_base_style_without_theme(monkeypatch) -> None:
    monkeypatch.setattr(type_help, "with_style", _marker)
    style = TextStyle(color="blue")

    rendered = format_type_for_help("list[str]", style)

    assert rendered == "<blue>list</blue><blue>[</blue><blue>str</blue><blue>]</blue>"

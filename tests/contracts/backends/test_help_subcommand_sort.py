import pytest

from interfacy import Interfacy
from interfacy.help.presets import InterfacyLayout
from interfacy.help.terminal import strip_ansi
from tests.fixtures.classes import TextTools
from tests.fixtures.commands import attach, greet, pow


class TodoCommands:
    def remove(self) -> str:
        return "remove"

    def add(self) -> str:
        return "add"


def _command_rows(help_text: str) -> list[str]:
    lines = strip_ansi(help_text).splitlines()
    heading = next(index for index, line in enumerate(lines) if line.lower() == "commands:")
    rows: list[str] = []
    for line in lines[heading + 1 :]:
        if not line.strip() or not line.startswith(" "):
            break

        rows.append(line)

    assert rows, "The commands section must contain listing rows"
    indent = min(len(line) - len(line.lstrip()) for line in rows)
    return [
        line.strip().split(maxsplit=1)[0]
        for line in rows
        if len(line) - len(line.lstrip()) == indent
    ]


def test_argparse_help_subcommand_sort_default_insert_order() -> None:
    parser = Interfacy(
        backend="argparse",
    )
    parser.add_command(pow)
    parser.add_command(greet)
    parser.add_command(attach)
    help_text = parser.build_parser().format_help()

    assert help_text.index("pow") < help_text.index("greet") < help_text.index("attach")


def test_argparse_help_subcommand_sort_alphabetical() -> None:
    parser = Interfacy(
        backend="argparse",
        help_subcommand_sort=["alphabetical"],
    )
    parser.add_command(pow)
    parser.add_command(greet)
    parser.add_command(attach)
    help_text = parser.build_parser().format_help()

    assert help_text.index("attach") < help_text.index("greet") < help_text.index("pow")


def test_argparse_help_subcommand_sort_layout_default_used_when_user_unset() -> None:
    parser = Interfacy(
        backend="argparse",
        help_layout=InterfacyLayout(help_subcommand_sort_default=["name_length_desc"]),
    )
    parser.add_command(pow, name="run")
    parser.add_command(greet, name="status")
    parser.add_command(attach, name="deploy-service")
    help_text = parser.build_parser().format_help()

    assert help_text.index("deploy-service") < help_text.index("status") < help_text.index("run")


def test_argparse_help_subcommand_sort_user_rules_override_layout_default() -> None:
    parser = Interfacy(
        backend="argparse",
        help_layout=InterfacyLayout(help_subcommand_sort_default=["alphabetical"]),
        help_subcommand_sort=["insert_order"],
    )
    parser.add_command(pow)
    parser.add_command(greet)
    parser.add_command(attach)
    help_text = parser.build_parser().format_help()

    assert help_text.index("pow") < help_text.index("greet") < help_text.index("attach")


def test_argparse_help_subcommand_sort_nested_name_length_desc() -> None:
    parser = Interfacy(
        backend="argparse",
        help_subcommand_sort=["name_length_desc"],
    )
    parser.add_command(TextTools, name="tools")
    root = parser.build_parser()
    help_text = root.format_help()

    assert _command_rows(help_text) == ["prefix-text", "repeat", "join"]
    usage = help_text.split("\n\n", maxsplit=1)[0]
    assert usage.index("prefix-text") < usage.index("repeat") < usage.index("join")


def test_argparse_help_subcommand_sort_per_command_override() -> None:
    parser = Interfacy(
        backend="argparse",
        help_subcommand_sort=["insert_order"],
    )
    parser.add_command(TodoCommands, help_subcommand_sort=["alphabetical"])
    root = parser.build_parser()
    help_text = root.format_help()

    assert _command_rows(help_text) == ["add", "remove"]
    usage = help_text.split("\n\n", maxsplit=1)[0]
    assert usage.index("add") < usage.index("remove")


def test_click_help_subcommand_sort_alphabetical_top_level() -> None:
    pytest.importorskip("click")
    from click import Context

    parser = Interfacy(
        backend="click",
        help_subcommand_sort=["alphabetical"],
    )
    parser.add_command(pow)
    parser.add_command(greet)
    parser.add_command(attach)
    root = parser.build_parser()
    help_text = root.get_help(Context(root))

    assert help_text.index("attach") < help_text.index("greet") < help_text.index("pow")


def test_click_help_subcommand_sort_nested_name_length_asc() -> None:
    pytest.importorskip("click")
    from click import Context

    parser = Interfacy(
        backend="click",
        help_subcommand_sort=["name_length_asc"],
    )
    parser.add_command(TextTools, name="tools")
    root = parser.build_parser()
    help_text = root.get_help(Context(root))

    assert _command_rows(help_text) == ["join", "repeat", "prefix-text"]
    usage = help_text.split("\n\n", maxsplit=1)[0]
    assert usage.index("join") < usage.index("repeat") < usage.index("prefix-text")


def test_click_help_subcommand_sort_per_command_override() -> None:
    pytest.importorskip("click")
    from click import Context

    parser = Interfacy(
        backend="click",
        help_subcommand_sort=["insert_order"],
    )
    parser.add_command(TodoCommands, help_subcommand_sort=["alphabetical"])
    root = parser.build_parser()
    help_text = root.get_help(Context(root))

    assert _command_rows(help_text) == ["add", "remove"]
    usage = help_text.split("\n\n", maxsplit=1)[0]
    assert usage.index("add") < usage.index("remove")

import pytest

from interfacy.appearance.layouts import InterfacyLayout
from interfacy.argparse_backend import Argparser
from tests.conftest import TextTools, attach, greet, pow


class TodoCommands:
    def remove(self) -> str:
        return "remove"

    def add(self) -> str:
        return "add"


def test_argparse_help_subcommand_sort_default_insert_order() -> None:
    parser = Argparser(sys_exit_enabled=False)
    parser.add_command(pow)
    parser.add_command(greet)
    parser.add_command(attach)
    help_text = parser.build_parser().format_help()

    assert help_text.index("pow") < help_text.index("greet") < help_text.index("attach")


def test_argparse_help_subcommand_sort_alphabetical() -> None:
    parser = Argparser(
        help_subcommand_sort=["alphabetical"],
        sys_exit_enabled=False,
    )
    parser.add_command(pow)
    parser.add_command(greet)
    parser.add_command(attach)
    help_text = parser.build_parser().format_help()

    assert help_text.index("attach") < help_text.index("greet") < help_text.index("pow")


def test_argparse_help_subcommand_sort_layout_default_used_when_user_unset() -> None:
    parser = Argparser(
        help_layout=InterfacyLayout(help_subcommand_sort_default=["name_length_desc"]),
        sys_exit_enabled=False,
    )
    parser.add_command(pow, name="run")
    parser.add_command(greet, name="status")
    parser.add_command(attach, name="deploy-service")
    help_text = parser.build_parser().format_help()

    assert help_text.index("deploy-service") < help_text.index("status") < help_text.index("run")


def test_argparse_help_subcommand_sort_user_rules_override_layout_default() -> None:
    parser = Argparser(
        help_layout=InterfacyLayout(help_subcommand_sort_default=["alphabetical"]),
        help_subcommand_sort=["insert_order"],
        sys_exit_enabled=False,
    )
    parser.add_command(pow)
    parser.add_command(greet)
    parser.add_command(attach)
    help_text = parser.build_parser().format_help()

    assert help_text.index("pow") < help_text.index("greet") < help_text.index("attach")


def test_argparse_help_subcommand_sort_nested_name_length_desc() -> None:
    parser = Argparser(
        help_subcommand_sort=["name_length_desc"],
        sys_exit_enabled=False,
    )
    parser.add_command(TextTools, name="tools")
    root = parser.build_parser()
    help_text = root.format_help()

    assert help_text.index("prefix-text") < help_text.index("repeat") < help_text.index("join")


def test_argparse_help_subcommand_sort_per_command_override() -> None:
    parser = Argparser(
        help_subcommand_sort=["insert_order"],
        sys_exit_enabled=False,
    )
    parser.add_command(TodoCommands, help_subcommand_sort=["alphabetical"])
    root = parser.build_parser()
    help_text = root.format_help()

    assert help_text.index("add") < help_text.index("remove")


def test_click_help_subcommand_sort_alphabetical_top_level() -> None:
    pytest.importorskip("click")
    from click import Context

    from interfacy import ClickParser

    parser = ClickParser(
        help_subcommand_sort=["alphabetical"],
        sys_exit_enabled=False,
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

    from interfacy import ClickParser

    parser = ClickParser(
        help_subcommand_sort=["name_length_asc"],
        sys_exit_enabled=False,
    )
    parser.add_command(TextTools, name="tools")
    root = parser.build_parser()
    help_text = root.get_help(Context(root))

    assert help_text.index("join") < help_text.index("repeat") < help_text.index("prefix-text")


def test_click_help_subcommand_sort_per_command_override() -> None:
    pytest.importorskip("click")
    from click import Context

    from interfacy import ClickParser

    parser = ClickParser(
        help_subcommand_sort=["insert_order"],
        sys_exit_enabled=False,
    )
    parser.add_command(TodoCommands, help_subcommand_sort=["alphabetical"])
    root = parser.build_parser()
    help_text = root.get_help(Context(root))

    assert help_text.index("add") < help_text.index("remove")

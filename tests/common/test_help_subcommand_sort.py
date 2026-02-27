import pytest

from interfacy.appearance.layouts import InterfacyLayout
from interfacy.argparse_backend import Argparser


def cmd_zeta() -> str:
    return "zeta"


def cmd_alpha() -> str:
    return "alpha"


def cmd_mu() -> str:
    return "mu"


class VerboseOps:
    def tiny(self) -> str:
        return "tiny"

    def moderate_size(self) -> str:
        return "moderate"

    def extraordinarily_verbose_operation(self) -> str:
        return "verbose"


def test_argparse_help_subcommand_sort_default_insert_order() -> None:
    parser = Argparser(sys_exit_enabled=False)
    parser.add_command(cmd_zeta, name="zeta-cmd")
    parser.add_command(cmd_alpha, name="alpha-cmd")
    parser.add_command(cmd_mu, name="mu-cmd")
    help_text = parser.build_parser().format_help()

    assert help_text.index("zeta-cmd") < help_text.index("alpha-cmd") < help_text.index("mu-cmd")


def test_argparse_help_subcommand_sort_alphabetical() -> None:
    parser = Argparser(
        help_subcommand_sort=["alphabetical"],
        sys_exit_enabled=False,
    )
    parser.add_command(cmd_zeta, name="zeta-cmd")
    parser.add_command(cmd_alpha, name="alpha-cmd")
    parser.add_command(cmd_mu, name="mu-cmd")
    help_text = parser.build_parser().format_help()

    assert help_text.index("alpha-cmd") < help_text.index("mu-cmd") < help_text.index("zeta-cmd")


def test_argparse_help_subcommand_sort_layout_default_used_when_user_unset() -> None:
    parser = Argparser(
        help_layout=InterfacyLayout(help_subcommand_sort_default=["name_length_desc"]),
        sys_exit_enabled=False,
    )
    parser.add_command(cmd_mu, name="mu")
    parser.add_command(cmd_zeta, name="zeta-command")
    parser.add_command(cmd_alpha, name="alpha")
    help_text = parser.build_parser().format_help()

    assert help_text.index("zeta-command") < help_text.index("alpha") < help_text.index("mu")


def test_argparse_help_subcommand_sort_user_rules_override_layout_default() -> None:
    parser = Argparser(
        help_layout=InterfacyLayout(help_subcommand_sort_default=["alphabetical"]),
        help_subcommand_sort=["insert_order"],
        sys_exit_enabled=False,
    )
    parser.add_command(cmd_zeta, name="zeta-cmd")
    parser.add_command(cmd_alpha, name="alpha-cmd")
    parser.add_command(cmd_mu, name="mu-cmd")
    help_text = parser.build_parser().format_help()

    assert help_text.index("zeta-cmd") < help_text.index("alpha-cmd") < help_text.index("mu-cmd")


def test_argparse_help_subcommand_sort_nested_name_length_desc() -> None:
    parser = Argparser(
        help_subcommand_sort=["name_length_desc"],
        sys_exit_enabled=False,
    )
    parser.add_command(VerboseOps, name="ops")
    root = parser.build_parser()
    help_text = root.format_help()

    assert (
        help_text.index("extraordinarily-verbose-operation")
        < help_text.index("moderate-size")
        < help_text.index("tiny")
    )


def test_click_help_subcommand_sort_alphabetical_top_level() -> None:
    pytest.importorskip("click")
    from click import Context

    from interfacy import ClickParser

    parser = ClickParser(
        help_subcommand_sort=["alphabetical"],
        sys_exit_enabled=False,
    )
    parser.add_command(cmd_zeta, name="zeta-cmd")
    parser.add_command(cmd_alpha, name="alpha-cmd")
    parser.add_command(cmd_mu, name="mu-cmd")
    root = parser.build_parser()
    help_text = root.get_help(Context(root))

    assert help_text.index("alpha-cmd") < help_text.index("mu-cmd") < help_text.index("zeta-cmd")


def test_click_help_subcommand_sort_nested_name_length_asc() -> None:
    pytest.importorskip("click")
    from click import Context

    from interfacy import ClickParser

    parser = ClickParser(
        help_subcommand_sort=["name_length_asc"],
        sys_exit_enabled=False,
    )
    parser.add_command(VerboseOps, name="ops")
    root = parser.build_parser()
    help_text = root.get_help(Context(root))

    assert (
        help_text.index("tiny")
        < help_text.index("moderate-size")
        < help_text.index("extraordinarily-verbose-operation")
    )

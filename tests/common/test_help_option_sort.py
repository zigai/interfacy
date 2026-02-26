import pytest

from interfacy.appearance.layouts import InterfacyLayout
from interfacy.argparse_backend import Argparser
from interfacy.naming.flag_strategy import DefaultFlagStrategy


def smart_options(
    *,
    zebra: int = 1,
    alpha: int,
    beta: bool = False,
    gamma: int = 2,
) -> tuple[int, int, bool, int]:
    return zebra, alpha, beta, gamma


def short_priority_options(
    *,
    aardvark: int = 1,
    alpha: int = 2,
    zeta: int = 3,
) -> tuple[int, int, int]:
    return aardvark, alpha, zeta


def test_argparse_default_help_option_sort_smart() -> None:
    parser = Argparser(
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        sys_exit_enabled=False,
    )
    parser.add_command(smart_options)
    help_text = parser.build_parser().format_help()

    assert help_text.index("--alpha") < help_text.index("--gamma") < help_text.index("--zebra")
    assert help_text.index("--zebra") < help_text.index("--beta")


def test_argparse_help_option_sort_short_first() -> None:
    parser = Argparser(
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        help_option_sort=["short_first", "alphabetical"],
        sys_exit_enabled=False,
    )
    parser.add_command(short_priority_options)
    help_text = parser.build_parser().format_help()

    assert help_text.index("--aardvark") < help_text.index("--zeta") < help_text.index("--alpha")


def test_argparse_help_option_sort_user_rules_override_layout_default() -> None:
    parser = Argparser(
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        help_layout=InterfacyLayout(help_option_sort_default=["alphabetical"]),
        help_option_sort=["bool_last", "alphabetical"],
        sys_exit_enabled=False,
    )
    parser.add_command(smart_options)
    help_text = parser.build_parser().format_help()

    assert help_text.index("--alpha") < help_text.index("--gamma") < help_text.index("--zebra")
    assert help_text.index("--zebra") < help_text.index("--beta")


def test_argparse_help_option_sort_layout_default_used_when_user_unset() -> None:
    parser = Argparser(
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        help_layout=InterfacyLayout(help_option_sort_default=["alphabetical"]),
        sys_exit_enabled=False,
    )
    parser.add_command(smart_options)
    help_text = parser.build_parser().format_help()

    assert help_text.index("--alpha") < help_text.index("--beta") < help_text.index("--gamma")
    assert help_text.index("--gamma") < help_text.index("--zebra")


def test_click_default_help_option_sort_smart() -> None:
    pytest.importorskip("click")
    from click import Context

    from interfacy import ClickParser

    parser = ClickParser(
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        sys_exit_enabled=False,
    )
    parser.add_command(smart_options)
    command = parser.build_parser()
    help_text = command.get_help(Context(command))

    assert help_text.index("--alpha") < help_text.index("--gamma") < help_text.index("--zebra")
    assert help_text.index("--zebra") < help_text.index("--beta")


def test_click_help_option_sort_user_rules_override_layout_default() -> None:
    pytest.importorskip("click")
    from click import Context

    from interfacy import ClickParser

    parser = ClickParser(
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        help_layout=InterfacyLayout(help_option_sort_default=["alphabetical"]),
        help_option_sort=["bool_last", "alphabetical"],
        sys_exit_enabled=False,
    )
    parser.add_command(smart_options)
    command = parser.build_parser()
    help_text = command.get_help(Context(command))

    assert help_text.index("--alpha") < help_text.index("--gamma") < help_text.index("--zebra")
    assert help_text.index("--zebra") < help_text.index("--beta")

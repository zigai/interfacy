import pytest

from interfacy.argparse_backend import Argparser
from interfacy.naming.flag_strategy import DefaultFlagStrategy


def unsorted_options(*, zeta: int = 1, alpha: int = 2, beta: int = 3) -> tuple[int, int, int]:
    return zeta, alpha, beta


def test_argparse_help_option_sort_declaration() -> None:
    parser = Argparser(
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        help_option_sort="declaration",
        sys_exit_enabled=False,
    )
    parser.add_command(unsorted_options)
    help_text = parser.build_parser().format_help()

    assert help_text.index("--zeta") < help_text.index("--alpha") < help_text.index("--beta")


def test_argparse_help_option_sort_alphabetical() -> None:
    parser = Argparser(
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        help_option_sort="alphabetical",
        sys_exit_enabled=False,
    )
    parser.add_command(unsorted_options)
    help_text = parser.build_parser().format_help()

    assert help_text.index("--alpha") < help_text.index("--beta") < help_text.index("--zeta")


def test_click_help_option_sort_declaration() -> None:
    pytest.importorskip("click")
    from click import Context

    from interfacy import ClickParser

    parser = ClickParser(
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        help_option_sort="declaration",
        sys_exit_enabled=False,
    )
    parser.add_command(unsorted_options)
    command = parser.build_parser()
    help_text = command.get_help(Context(command))

    assert help_text.index("--zeta") < help_text.index("--alpha") < help_text.index("--beta")


def test_click_help_option_sort_alphabetical() -> None:
    pytest.importorskip("click")
    from click import Context

    from interfacy import ClickParser

    parser = ClickParser(
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        help_option_sort="alphabetical",
        sys_exit_enabled=False,
    )
    parser.add_command(unsorted_options)
    command = parser.build_parser()
    help_text = command.get_help(Context(command))

    assert help_text.index("--alpha") < help_text.index("--beta") < help_text.index("--zeta")

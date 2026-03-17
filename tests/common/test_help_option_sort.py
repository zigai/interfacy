import pytest

from interfacy.appearance.layouts import InterfacyLayout
from interfacy.argparse_backend import Argparser
from interfacy.naming.flag_strategy import DefaultFlagStrategy


def smart_options(
    *,
    environment: str,
    replicas: int = 2,
    dry_run: bool = False,
    timeout: int = 30,
) -> tuple[str, int, bool, int]:
    return environment, replicas, dry_run, timeout


def short_priority_options(
    *,
    api_key: int = 1,
    account_id: int = 2,
    zeta: int = 3,
) -> tuple[int, int, int]:
    return api_key, account_id, zeta


def test_argparse_default_help_option_sort_smart() -> None:
    parser = Argparser(
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        sys_exit_enabled=False,
    )
    parser.add_command(smart_options)
    help_text = parser.build_parser().format_help()

    assert (
        help_text.index("--environment")
        < help_text.index("--replicas")
        < help_text.index("--timeout")
    )
    assert help_text.index("--timeout") < help_text.index("--dry-run")


def test_argparse_help_option_sort_short_first() -> None:
    parser = Argparser(
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        help_option_sort=["short_first", "alphabetical"],
        sys_exit_enabled=False,
    )
    parser.add_command(short_priority_options)
    help_text = parser.build_parser().format_help()

    assert (
        help_text.index("--api-key") < help_text.index("--zeta") < help_text.index("--account-id")
    )


def test_argparse_help_option_sort_user_rules_override_layout_default() -> None:
    parser = Argparser(
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        help_layout=InterfacyLayout(help_option_sort_default=["alphabetical"]),
        help_option_sort=["bool_last", "alphabetical"],
        sys_exit_enabled=False,
    )
    parser.add_command(smart_options)
    help_text = parser.build_parser().format_help()

    assert (
        help_text.index("--environment")
        < help_text.index("--replicas")
        < help_text.index("--timeout")
    )
    assert help_text.index("--timeout") < help_text.index("--dry-run")


def test_argparse_help_option_sort_layout_default_used_when_user_unset() -> None:
    parser = Argparser(
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        help_layout=InterfacyLayout(help_option_sort_default=["alphabetical"]),
        sys_exit_enabled=False,
    )
    parser.add_command(smart_options)
    help_text = parser.build_parser().format_help()

    assert (
        help_text.index("--dry-run")
        < help_text.index("--environment")
        < help_text.index("--replicas")
    )
    assert help_text.index("--replicas") < help_text.index("--timeout")


def test_argparse_help_option_sort_per_command_override() -> None:
    parser = Argparser(
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        help_option_sort=["alphabetical"],
        sys_exit_enabled=False,
    )
    parser.add_command(smart_options, help_option_sort=["bool_last", "alphabetical"])
    help_text = parser.build_parser().format_help()
    options_section = help_text.split("options:", maxsplit=1)[1]

    assert (
        options_section.index("--environment")
        < options_section.index("--replicas")
        < options_section.index("--timeout")
    )
    assert options_section.index("--timeout") < options_section.index("--dry-run")


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

    assert (
        help_text.index("--environment")
        < help_text.index("--replicas")
        < help_text.index("--timeout")
    )
    assert help_text.index("--timeout") < help_text.index("--dry-run")


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

    assert (
        help_text.index("--environment")
        < help_text.index("--replicas")
        < help_text.index("--timeout")
    )
    assert help_text.index("--timeout") < help_text.index("--dry-run")


def test_click_help_option_sort_per_command_override() -> None:
    pytest.importorskip("click")
    from click import Context

    from interfacy import ClickParser

    parser = ClickParser(
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        help_option_sort=["alphabetical"],
        sys_exit_enabled=False,
    )
    parser.add_command(smart_options, help_option_sort=["bool_last", "alphabetical"])
    command = parser.build_parser()
    help_text = command.get_help(Context(command))
    options_section = help_text.split("options:", maxsplit=1)[1]

    assert (
        options_section.index("--environment")
        < options_section.index("--replicas")
        < options_section.index("--timeout")
    )
    assert options_section.index("--timeout") < options_section.index("--dry-run")

import pytest

from interfacy import Interfacy
from interfacy.help.presets import InterfacyLayout
from interfacy.naming.flag_strategy import DefaultFlagStrategy


def _help_section(help_text: str, heading: str) -> str:
    for candidate in (f"{heading}:", f"{heading.capitalize()}:"):
        parts = help_text.split(candidate, maxsplit=1)
        if len(parts) == 2:
            return parts[1]

    raise AssertionError(f"Section {heading!r} not found in help text:\n{help_text}")


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
    parser = Interfacy(
        backend="argparse",
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
    )
    parser.add_command(smart_options)
    help_text = parser.build_parser().format_help()
    options_section = _help_section(help_text, "options")

    assert (
        options_section.index("--environment")
        < options_section.index("--replicas")
        < options_section.index("--timeout")
    )
    assert options_section.index("--timeout") < options_section.index("--dry-run")


def test_argparse_help_option_sort_short_first() -> None:
    parser = Interfacy(
        backend="argparse",
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        help_option_sort=["short_first", "alphabetical"],
    )
    parser.add_command(short_priority_options)
    help_text = parser.build_parser().format_help()
    options_section = _help_section(help_text, "options")

    assert (
        options_section.index("--api-key")
        < options_section.index("--zeta")
        < options_section.index("--account-id")
    )


def test_argparse_help_option_sort_user_rules_override_layout_default() -> None:
    parser = Interfacy(
        backend="argparse",
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        help_layout=InterfacyLayout(help_option_sort_default=["alphabetical"]),
        help_option_sort=["bool_last", "alphabetical"],
    )
    parser.add_command(smart_options)
    help_text = parser.build_parser().format_help()
    options_section = _help_section(help_text, "options")

    assert (
        options_section.index("--environment")
        < options_section.index("--replicas")
        < options_section.index("--timeout")
    )
    assert options_section.index("--timeout") < options_section.index("--dry-run")


def test_argparse_help_option_sort_layout_default_used_when_user_unset() -> None:
    parser = Interfacy(
        backend="argparse",
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        help_layout=InterfacyLayout(help_option_sort_default=["alphabetical"]),
    )
    parser.add_command(smart_options)
    help_text = parser.build_parser().format_help()
    options_section = _help_section(help_text, "options")

    assert (
        options_section.index("--dry-run")
        < options_section.index("--environment")
        < options_section.index("--replicas")
    )
    assert options_section.index("--replicas") < options_section.index("--timeout")


def test_argparse_help_option_sort_per_command_override() -> None:
    parser = Interfacy(
        backend="argparse",
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        help_option_sort=["alphabetical"],
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

    parser = Interfacy(
        backend="click",
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
    )
    parser.add_command(smart_options)
    command = parser.build_parser()
    help_text = command.get_help(Context(command))
    options_section = _help_section(help_text, "options")

    assert (
        options_section.index("--environment")
        < options_section.index("--replicas")
        < options_section.index("--timeout")
    )
    assert options_section.index("--timeout") < options_section.index("--dry-run")


def test_click_help_option_sort_user_rules_override_layout_default() -> None:
    pytest.importorskip("click")
    from click import Context

    parser = Interfacy(
        backend="click",
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        help_layout=InterfacyLayout(help_option_sort_default=["alphabetical"]),
        help_option_sort=["bool_last", "alphabetical"],
    )
    parser.add_command(smart_options)
    command = parser.build_parser()
    help_text = command.get_help(Context(command))
    options_section = _help_section(help_text, "options")

    assert (
        options_section.index("--environment")
        < options_section.index("--replicas")
        < options_section.index("--timeout")
    )
    assert options_section.index("--timeout") < options_section.index("--dry-run")


def test_click_help_option_sort_per_command_override() -> None:
    pytest.importorskip("click")
    from click import Context

    parser = Interfacy(
        backend="click",
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        help_option_sort=["alphabetical"],
    )
    parser.add_command(smart_options, help_option_sort=["bool_last", "alphabetical"])
    command = parser.build_parser()
    help_text = command.get_help(Context(command))
    options_section = _help_section(help_text, "options")

    assert (
        options_section.index("--environment")
        < options_section.index("--replicas")
        < options_section.index("--timeout")
    )
    assert options_section.index("--timeout") < options_section.index("--dry-run")

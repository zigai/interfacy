import argparse

import pytest

from interfacy import Interfacy
from interfacy.naming import DefaultFlagStrategy


def build_parser_with_custom_name(custom_name: str) -> tuple[Interfacy, argparse.ArgumentParser]:
    def default(a: int) -> int:
        return a

    def custom(a: int) -> int:
        return a

    builder = Interfacy(
        backend="argparse",
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        full_error_traceback=True,
        help_layout=None,
        print_result=False,
    )

    builder.add_command(default)
    builder.add_command(custom, name=custom_name)
    parser = builder.build_parser()
    return builder, parser


def build_parser_with_aliases(aliases: list[str]) -> tuple[Interfacy, argparse.ArgumentParser]:
    def primary(a: int) -> int:
        return a

    def secondary(a: int) -> int:
        return a

    builder = Interfacy(
        backend="argparse",
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        full_error_traceback=True,
        help_layout=None,
        print_result=False,
    )

    builder.add_command(primary, aliases=aliases)
    builder.add_command(secondary)
    parser = builder.build_parser()
    return builder, parser


class TestCustomCommandNames:
    @pytest.mark.parametrize("custom_name", ["CustomCommand"])
    def test_help_displays_custom_name_verbatim(self, custom_name: str):
        """Verify that the generated help text displays the custom command name."""
        _, parser = build_parser_with_custom_name(custom_name)
        help_text = parser.format_help()
        assert custom_name in help_text
        assert "\n  custom\n" not in help_text


class TestCommandAliases:
    def test_help_lists_aliases(self):
        """Verify that command aliases are listed in the help output."""
        aliases = ["pick", "choose"]
        _, parser = build_parser_with_aliases(aliases)
        help_text = parser.format_help()
        for alias in aliases:
            assert alias in help_text

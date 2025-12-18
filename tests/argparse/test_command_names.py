import argparse

import pytest

from interfacy.argparse_backend import Argparser
from interfacy.argparse_backend.argument_parser import namespace_to_dict
from interfacy.naming import DefaultFlagStrategy


def get_subparser_names(parser: argparse.ArgumentParser) -> list[str]:
    actions = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    assert actions, "No subparsers action found on the parser"
    return list(actions[0].choices.keys())


def build_parser_with_custom_name(custom_name: str) -> tuple[Argparser, argparse.ArgumentParser]:
    def default(a: int) -> int:
        return a

    def custom(a: int) -> int:
        return a

    builder = Argparser(
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        sys_exit_enabled=False,
        full_error_traceback=True,
        help_layout=None,
        print_result=False,
    )

    builder.add_command(default)
    builder.add_command(custom, name=custom_name)
    parser = builder.build_parser()
    return builder, parser


def build_parser_with_aliases(aliases: list[str]) -> tuple[Argparser, argparse.ArgumentParser]:
    def primary(a: int) -> int:
        return a

    def secondary(a: int) -> int:
        return a

    builder = Argparser(
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        sys_exit_enabled=False,
        full_error_traceback=True,
        help_layout=None,
        print_result=False,
    )

    builder.add_command(primary, aliases=aliases)
    builder.add_command(secondary)
    parser = builder.build_parser()
    return builder, parser


class TestCustomCommandNames:
    @pytest.mark.parametrize("custom_name", ["CustomCommand", "_Custom__Command__NAME"])
    def test_subparsers_use_custom_name_verbatim(self, custom_name: str):
        """Verify that argparse subparsers use the provided custom name instead of the function name."""
        _, parser = build_parser_with_custom_name(custom_name)
        names = get_subparser_names(parser)
        assert custom_name in names
        assert "custom" not in names

    @pytest.mark.parametrize("custom_name", ["CustomCommand"])
    def test_help_displays_custom_name_verbatim(self, custom_name: str):
        """Verify that the generated help text displays the custom command name."""
        _, parser = build_parser_with_custom_name(custom_name)

        epilog = parser.epilog or ""
        assert isinstance(epilog, str)
        assert custom_name in epilog
        assert "custom" not in epilog

    @pytest.mark.parametrize("custom_name", ["CustomCommand"])
    def test_runner_executes_custom_command_when_namespace_uses_custom_key(self, custom_name: str):
        """Verify that the runner correctly executes the command when the custom name is present in parsed args."""
        builder, parser = build_parser_with_custom_name(custom_name)

        args = [custom_name, "2"]

        namespace = namespace_to_dict(parser.parse_args(args))

        from interfacy.argparse_backend.runner import ArgparseRunner

        runner = ArgparseRunner(
            namespace=namespace,
            builder=builder,
            args=args,
            parser=parser,
        )
        result = runner.run()
        assert result == 2


class TestCommandAliases:
    def test_subparsers_include_aliases(self):
        """Verify that command aliases are registered as additional subparser choices."""
        aliases = ["pick", "choose"]
        _, parser = build_parser_with_aliases(aliases)
        names = get_subparser_names(parser)
        for alias in aliases:
            assert alias in names

    def test_help_lists_aliases(self):
        """Verify that command aliases are listed in the help output."""
        aliases = ["pick", "choose"]
        _, parser = build_parser_with_aliases(aliases)
        epilog = parser.epilog or ""
        for alias in aliases:
            assert alias in epilog

    def test_runner_executes_command_via_alias(self):
        """Verify that the command can be executed by invoking one of its aliases."""
        aliases = ["pick"]
        builder, parser = build_parser_with_aliases(aliases)
        args = [aliases[0], "3"]
        namespace = namespace_to_dict(parser.parse_args(args))

        from interfacy.argparse_backend.runner import ArgparseRunner

        runner = ArgparseRunner(
            namespace=namespace,
            builder=builder,
            args=args,
            parser=parser,
        )
        result = runner.run()
        assert result == 3

import argparse

import pytest

from interfacy.argparse_backend import Argparser
from interfacy.argparse_backend.argument_parser import namespace_to_dict
from interfacy.flag_generator import BasicFlagGenerator


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
        flag_strategy=BasicFlagGenerator(style="required_positional"),
        sys_exit_enabled=False,
        full_error_traceback=True,
        theme=None,
        print_result=False,
    )

    builder.add_command(default)
    builder.add_command(custom, name=custom_name)
    parser = builder.build_parser()
    return builder, parser


class TestCustomCommandNames:
    @pytest.mark.parametrize("custom_name", ["CustomCommand", "My__Weird__Name"])
    def test_subparsers_use_custom_name_verbatim(self, custom_name: str):
        _, parser = build_parser_with_custom_name(custom_name)
        names = get_subparser_names(parser)
        assert custom_name in names
        assert "custom" not in names

    @pytest.mark.parametrize("custom_name", ["CustomCommand"])
    def test_help_displays_custom_name_verbatim(self, custom_name: str):
        _, parser = build_parser_with_custom_name(custom_name)

        epilog = parser.epilog or ""
        assert isinstance(epilog, str)
        assert custom_name in epilog
        assert "custom" not in epilog

    @pytest.mark.parametrize("custom_name", ["CustomCommand"])
    def test_runner_executes_custom_command_when_namespace_uses_custom_key(self, custom_name: str):
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

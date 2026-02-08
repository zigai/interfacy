import argparse

from interfacy.argparse_backend import Argparser
from interfacy.naming import DefaultFlagStrategy


def _subparser_names(parser: argparse.ArgumentParser) -> list[str]:
    actions = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    assert actions, "No subparsers action found on the parser"
    return list(actions[0].choices.keys())


def test_parser_from_multiple_commands_registers_and_builds() -> None:
    def inc(value: int) -> int:
        return value + 1

    def dec(value: int) -> int:
        return value - 1

    builder = Argparser(
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        sys_exit_enabled=False,
        full_error_traceback=True,
        help_layout=None,
        print_result=False,
    )

    parser = builder.parser_from_multiple_commands(inc, dec)
    assert "inc" in _subparser_names(parser)
    assert "dec" in _subparser_names(parser)
    assert builder.run(args=["inc", "2"]) == 3

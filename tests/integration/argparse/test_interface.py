import argparse

from interfacy import Interfacy
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

    builder = Interfacy(
        backend="argparse",
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        full_error_traceback=True,
        help_layout=None,
        print_result=False,
    )

    builder.add_command(inc)
    builder.add_command(dec)
    parser = builder.build_parser()
    assert "inc" in _subparser_names(parser)
    assert "dec" in _subparser_names(parser)
    assert builder.invoke(args=["inc", "2"]) == 3

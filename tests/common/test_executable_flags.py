from __future__ import annotations

import pytest

from interfacy import CommandGroup, ExecutableFlag
from interfacy.exceptions import ReservedFlagError
from tests.conftest import greet, pow


def _version_flag(text: str = "interfacy 1.2.3") -> ExecutableFlag:
    return ExecutableFlag(
        flags=("-V", "--version"),
        handler=lambda: text,
        help="Show version and exit.",
    )


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_root_executable_flag_runs_before_command_dispatch(parser, capsys) -> None:
    parser.executable_flags = [_version_flag()]
    parser.add_command(greet)

    result = parser.run(args=["--version"])

    assert isinstance(result, SystemExit)
    assert result.code == 0

    captured = capsys.readouterr()
    assert "interfacy 1.2.3" in captured.out + captured.err


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_leaf_command_executable_flag_runs_on_command_level(parser, capsys) -> None:
    about_flag = ExecutableFlag(
        flags=("--about",),
        handler=lambda: "friendly greeter",
        help="Show command metadata and exit.",
    )
    parser.add_command(greet, executable_flags=[about_flag])
    parser.add_command(pow)

    result = parser.run(args=["greet", "--about"])

    assert isinstance(result, SystemExit)
    assert result.code == 0

    captured = capsys.readouterr()
    assert "friendly greeter" in captured.out + captured.err


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_group_executable_flag_short_circuits_before_missing_subcommand(parser, capsys) -> None:
    tools = CommandGroup("tools")
    tools.add_command(greet)
    parser.add_command(
        tools,
        executable_flags=[
            ExecutableFlag(
                flags=("--about",),
                handler=lambda: "tool suite",
                help="Show tool suite metadata and exit.",
            )
        ],
    )

    result = parser.run(args=["tools", "--about"])

    assert isinstance(result, SystemExit)
    assert result.code == 0

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "tool suite" in combined
    assert "commands:" not in combined.lower()


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_single_root_help_merges_parser_and_command_executable_flags(parser) -> None:
    parser.executable_flags = [_version_flag()]
    parser.add_command(
        greet,
        executable_flags=[
            ExecutableFlag(
                flags=("--about",),
                handler=lambda: None,
                help="Show command metadata and exit.",
            )
        ],
    )

    if parser.__class__.__name__ == "Argparser":
        help_text = parser.build_parser().format_help()
    else:
        import click

        command = parser.build_parser()
        help_text = command.get_help(click.Context(command))

    assert "--help" in help_text
    assert "--version" in help_text
    assert "--about" in help_text


@pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
def test_executable_flag_collision_with_generated_option_is_rejected(parser) -> None:
    def versioned(*, version: int = 1) -> int:
        return version

    parser.add_command(versioned, executable_flags=[ExecutableFlag(("--version",), lambda: None)])

    with pytest.raises(ReservedFlagError):
        parser.build_parser()


def test_root_executable_flag_cannot_reuse_native_help() -> None:
    from interfacy import Argparser

    with pytest.raises(ReservedFlagError):
        Argparser(executable_flags=[ExecutableFlag(("--help",), lambda: None)])

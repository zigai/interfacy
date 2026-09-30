from __future__ import annotations

import pytest

from interfacy.backends.argparse import ArgumentParser
from interfacy.exceptions import InterfacyExit, UsageError


def build_parser(*, sys_exit_enabled: bool = True) -> ArgumentParser:
    parser = ArgumentParser(prog="deploy", sys_exit_enabled=sys_exit_enabled)
    parser.add_argument("environment", choices=("staging", "production"))
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("status").add_argument("--count", type=int)

    return parser


@pytest.mark.parametrize(
    ("args", "usage"),
    [
        (["--help"], "usage: deploy [--help] ENVIRONMENT {status}"),
        (["staging", "status", "--help"], "usage: deploy ENVIRONMENT status [--help] [--count]"),
    ],
)
def test_manual_parser_help_prints_help_and_exits_zero(
    capsys: pytest.CaptureFixture[str],
    args: list[str],
    usage: str,
) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(args)

    captured = capsys.readouterr()
    assert excinfo.value.code == 0
    assert captured.out.splitlines()[0] == usage
    assert captured.err == ""


@pytest.mark.parametrize(
    ("args", "usage", "error_prefix"),
    [
        (
            ["qa"],
            "usage: deploy [--help] ENVIRONMENT {status} ...",
            "deploy: error: argument ENVIRONMENT: invalid choice: 'qa'",
        ),
        (
            ["staging", "status", "--count", "x"],
            "usage: deploy ENVIRONMENT status [--help] [--count COUNT]",
            "deploy ENVIRONMENT status: error: argument --count: invalid int value: 'x'",
        ),
    ],
)
def test_manual_parser_usage_error_reports_to_stderr_and_exits_two(
    capsys: pytest.CaptureFixture[str],
    args: list[str],
    usage: str,
    error_prefix: str,
) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(args)

    captured = capsys.readouterr()
    usage_line, error_line = captured.err.splitlines()
    assert excinfo.value.code == 2
    assert captured.out == ""
    assert usage_line == usage
    assert error_line.startswith(error_prefix)


@pytest.mark.parametrize("args", [["--help"], ["staging", "status", "--help"]])
def test_manual_parser_without_sys_exit_raises_interfacy_exit_for_help(
    capsys: pytest.CaptureFixture[str],
    args: list[str],
) -> None:
    parser = build_parser(sys_exit_enabled=False)

    with pytest.raises(InterfacyExit) as excinfo:
        parser.parse_args(args)

    assert excinfo.value.code == 0
    assert capsys.readouterr().out.startswith("usage: deploy")


def test_manual_parser_without_sys_exit_raises_usage_error_from_subcommand(
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = build_parser(sys_exit_enabled=False)

    with pytest.raises(UsageError) as excinfo:
        parser.parse_args(["staging", "status", "--count", "x"])

    assert str(excinfo.value) == "argument --count: invalid int value: 'x'"
    assert excinfo.value.usage == "usage: deploy ENVIRONMENT status [--help] [--count COUNT]\n"
    assert capsys.readouterr().err == ""

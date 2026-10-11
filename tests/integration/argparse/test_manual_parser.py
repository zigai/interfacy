from __future__ import annotations

import argparse
import re

import pytest

from interfacy.backends.argparse import ArgumentParser
from interfacy.common.terminal import strip_ansi
from interfacy.exceptions import InterfacyExit, UsageError
from interfacy.help import Modern


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


def test_nested_manual_parser_uses_leaf_metavar_for_append_action() -> None:
    parser = ArgumentParser(prog="manual")
    subparsers = parser.add_subparsers(dest="command", required=True)
    deploy = subparsers.add_parser("deploy")
    deploy.add_argument("--tag", action="append", default=None, help="Attach a tag.")

    help_text = deploy.format_help()
    assert "--tag TAG" in help_text
    assert "DEPLOY__TAG" not in help_text


def test_argument_parser_defaults_to_standard_layout() -> None:
    parser = ArgumentParser(prog="manual")
    parser.add_argument("--level", type=int, default=2, help="Set output level.")

    help_text = parser.format_help()

    assert "usage: manual [--help] [--level]" in help_text
    assert "usage: manual [--help] [--level LEVEL]" not in help_text
    assert "--level LEVEL" in help_text
    assert "[default: 2]" in help_text
    assert "Defaults to 2." not in help_text


def test_argument_parser_disables_argparse_usage_colors_when_python_colors_forced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTHON_COLORS", "1")
    parser = ArgumentParser(prog="agentctl pi", sys_exit_enabled=False)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("new", "send", "skill", "slash", "steer", "rename"):
        subparsers.add_parser(name)

    with pytest.raises(UsageError) as excinfo:
        parser.parse_args(["status"])

    assert "invalid choice: 'status'" in str(excinfo.value)
    assert excinfo.value.usage == strip_ansi(excinfo.value.usage or "")


def test_manual_argument_parser_help_position_keeps_long_option_description_inline() -> None:
    parser = ArgumentParser(prog="manual", help_position=42)
    parser.add_argument(
        "-d",
        "--disable-job-duration-limit",
        action="store_true",
        help="Disable the per-job duration limit.",
    )

    help_text = parser.format_help()

    assert re.search(
        r"^\s*-d, --disable-job-duration-limit\s+Disable the per-job duration limit\.$",
        help_text,
        re.MULTILINE,
    )


def test_manual_modern_layout_renders_template_details_without_attached_schema() -> None:
    parser = ArgumentParser(
        prog="deploy",
        description="Deploy an application build.",
        help_layout=Modern(),
    )
    parser.add_argument(
        "environment",
        choices=("staging", "production"),
        help="Target environment.",
    )
    parser.add_argument("--region", default="us-east-1", help="Cloud region.")
    parser.add_argument(
        "--strategy",
        choices=("rolling", "blue-green", "canary"),
        default="rolling",
        help="Deployment strategy.",
    )
    parser.add_argument(
        "--color",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable color output.",
    )

    help_text = re.sub(r"\x1b\[[0-9;]*m", "", parser.format_help())

    assert "↳ choices: staging, production" in help_text
    assert "↳ default: us-east-1 | type: str" in help_text
    assert "↳ default: rolling | choices: rolling, blue-green," in help_text
    assert "canary" in help_text
    assert "--no-color" in help_text
    assert "↳ default: true" in help_text


def test_manual_modern_layout_lists_subcommands_without_attached_schema() -> None:
    parser = ArgumentParser(
        prog="manual",
        description="Manual CLI.",
        help_layout=Modern(),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("clone", help="Clone a repository.")
    subparsers.add_parser("status", help="Show current status.")

    help_text = re.sub(r"\x1b\[[0-9;]*m", "", parser.format_help())

    assert "{clone,status}" in help_text
    assert re.search(r"^\s*clone\s+Clone a repository\.$", help_text, re.MULTILINE)
    assert re.search(r"^\s*status\s+Show current status\.$", help_text, re.MULTILINE)

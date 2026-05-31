from __future__ import annotations

import sys

import pytest
from objinspect import Function

from interfacy.appearance.layouts import InterfacyLayout
from interfacy.argparse_backend import Argparser
from interfacy.exceptions import ConfigurationError
from interfacy.executable_flag import ExecutableFlag
from interfacy.schema.schema import Command, ParserSchema


def alpha() -> str:
    return "alpha"


def beta() -> str:
    return "beta"


def test_build_parser_without_commands_raises_configuration_error() -> None:
    parser = Argparser(sys_exit_enabled=False)

    with pytest.raises(ConfigurationError, match="No commands were provided"):
        parser.build_parser()


def test_install_tab_completion_warns_when_argcomplete_is_missing(
    monkeypatch,
    capsys,
) -> None:
    parser = Argparser(sys_exit_enabled=False)
    cli = parser._new_parser()

    monkeypatch.setitem(sys.modules, "argcomplete", None)

    parser.install_tab_completion(cli)

    captured = capsys.readouterr()
    assert "argcomplete not installed" in captured.err


def test_schema_root_description_epilog_and_command_epilog_are_combined() -> None:
    layout = InterfacyLayout()
    command = Command(
        obj=Function(alpha),
        canonical_name="alpha",
        cli_name="alpha",
        aliases=(),
        raw_description="Alpha command.",
        raw_epilog="Command tail.",
        help_layout=layout,
    )
    schema = ParserSchema(
        raw_description="Root description.",
        raw_epilog="Root tail.",
        commands={"alpha": command},
        command_key="command",
        allow_args_from_file=True,
        pipe_targets=None,
        theme=layout,
    )

    cli = Argparser(sys_exit_enabled=False)._build_from_schema(schema)
    help_text = cli.format_help()

    assert "Root description." in help_text
    assert "Command tail." in help_text
    assert "Root tail." in help_text


def test_multi_command_schema_registers_aliases_and_executable_flags() -> None:
    layout = InterfacyLayout()
    schema = ParserSchema(
        raw_description=None,
        raw_epilog=None,
        commands={
            "alpha": Command(
                obj=Function(alpha),
                canonical_name="alpha",
                cli_name="alpha",
                aliases=("a",),
                raw_description="Alpha command.",
                help_layout=layout,
            ),
            "beta": Command(
                obj=Function(beta),
                canonical_name="beta",
                cli_name="beta",
                aliases=(),
                raw_description="Beta command.",
                help_layout=layout,
            ),
        },
        command_key="command",
        allow_args_from_file=True,
        pipe_targets=None,
        theme=layout,
        executable_flags=[ExecutableFlag(("--version",), lambda: "1.0", help="Show version.")],
    )

    cli = Argparser(sys_exit_enabled=False)._build_from_schema(schema)
    namespace = cli.parse_args(["a"])
    help_text = cli.format_help()

    assert namespace.command == "a"
    assert "--version" in help_text
    assert "alpha" in help_text
    assert "beta" in help_text

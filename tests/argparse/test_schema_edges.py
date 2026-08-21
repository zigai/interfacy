from __future__ import annotations

import sys

import pytest
from objinspect import Function

from interfacy import Param, params
from interfacy.appearance.layouts import InterfacyLayout
from interfacy.argparse_backend import Argparser, ArgumentParser
from interfacy.argparse_backend.argument_parser import namespace_to_dict
from interfacy.exceptions import ConfigurationError
from interfacy.executable_flag import ExecutableFlag
from interfacy.naming import DefaultFlagStrategy
from interfacy.schema.schema import Command, ParserSchema


def alpha() -> str:
    return "alpha"


def beta() -> str:
    return "beta"


@params(config=Param(kind="positional", metavar="CONFIG"))
def validate_config(config: str | None = None) -> str | None:
    """Validate configuration."""
    return config


def test_build_parser_without_commands_raises_configuration_error() -> None:
    parser = Argparser(sys_exit_enabled=False)

    with pytest.raises(ConfigurationError, match="No commands were provided"):
        parser.build_parser()


def test_negative_named_bool_help_shows_only_declared_flag() -> None:
    parser = Argparser(sys_exit_enabled=False)

    def run(*, no_stdio: bool = False) -> bool:
        return no_stdio

    parser.add_command(run)
    help_text = parser.build_parser().format_help()

    assert "--no-stdio" in help_text
    assert "--stdio" not in help_text
    assert "--help" in help_text


def test_configured_help_alias_accepts_short_help_flag() -> None:
    parser = Argparser(sys_exit_enabled=False, help_flags=("-h", "--help"))

    def run() -> None:
        """Run command."""

    parser.add_command(run)
    help_text = parser.build_parser().format_help()

    assert "-h, --help" in help_text


def test_configured_help_alias_applies_to_subcommands(capsys) -> None:
    parser = Argparser(sys_exit_enabled=False, help_flags=("-h", "--help"))
    parser.add_command(alpha)
    parser.add_command(beta)

    result = parser.run(args=["alpha", "-h"])

    assert isinstance(result, SystemExit)
    assert result.code == 0
    assert "-h, --help" in capsys.readouterr().out


def test_optional_positional_usage_shows_optional_metavar() -> None:
    parser = Argparser(sys_exit_enabled=False)
    parser.add_command(validate_config)

    help_text = parser.build_parser().format_help()

    assert "[CONFIG]" in help_text


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


def test_argument_name_containing_nest_separator_is_not_split() -> None:
    def show(*, foo__bar: str = "default") -> str:
        return foo__bar

    parser = Argparser(
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        print_result=False,
        sys_exit_enabled=False,
    )

    assert parser.run(show, args=["--foo-bar", "supplied"]) == "supplied"


def test_subparser_parent_does_not_mutate_reusable_parent_parser() -> None:
    default = object()
    parent = ArgumentParser(add_help=False)
    parent.add_argument("--value", default=default)
    root = ArgumentParser()
    subparsers = root.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run", parents=[parent])

    assert namespace_to_dict(root.parse_args(["run", "--value", "child"])) == {
        "command": "run",
        "run": {"value": "child"},
    }
    assert namespace_to_dict(root.parse_args(["run"]))["run"]["value"] is default
    assert namespace_to_dict(parent.parse_args(["--value", "parent"])) == {"value": "parent"}

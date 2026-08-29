from __future__ import annotations

import sys

import pytest
from objinspect import Function

from interfacy import Interfacy, Param, params
from interfacy.argparse_backend import ArgparseBackend, ArgparseSession
from interfacy.engine.backend import BackendConfig
from interfacy.exceptions import ConfigurationError
from interfacy.executable_flag import ExecutableFlag
from interfacy.help.presets import StandardLayout
from interfacy.help.renderer import SchemaHelpRenderer
from interfacy.schema.schema import Command, ParserSchema


class _SchemaHelpPipeline:
    def __init__(self, schema: ParserSchema) -> None:
        self._schema = schema

    def render(
        self,
        command_path: tuple[str, ...],
        terminal_width: int | None = None,
    ) -> str:
        renderer = SchemaHelpRenderer(StandardLayout(), terminal_width=terminal_width)
        if not command_path:
            return renderer.render_parser_help(self._schema, "main")
        command = self._schema.get_command(command_path[-1])
        return renderer.render_command_help(
            command,
            " ".join(command_path),
            parser_schema=self._schema,
        )


def _compile_schema(schema: ParserSchema) -> ArgparseSession:
    return ArgparseBackend().compile(
        schema,
        _SchemaHelpPipeline(schema),
        BackendConfig(help_layout=StandardLayout()),
    )


def alpha() -> str:
    return "alpha"


def beta() -> str:
    return "beta"


@params(config=Param(kind="positional", metavar="CONFIG"))
def validate_config(config: str | None = None) -> str | None:
    """Validate configuration."""
    return config


def test_build_parser_without_commands_raises_configuration_error() -> None:
    parser = Interfacy(
        backend="argparse",
    )

    with pytest.raises(ConfigurationError, match="No commands were provided"):
        parser.build_parser()


def test_negative_named_bool_help_shows_only_declared_flag() -> None:
    parser = Interfacy(
        backend="argparse",
    )

    def run(*, no_stdio: bool = False) -> bool:
        return no_stdio

    parser.add_command(run)
    help_text = parser.build_parser().format_help()

    assert "--no-stdio" in help_text
    assert "--stdio" not in help_text
    assert "--help" in help_text


def test_configured_help_alias_accepts_short_help_flag() -> None:
    parser = Interfacy(backend="argparse", help_flags=("-h", "--help"))

    def run() -> None:
        """Run command."""

    parser.add_command(run)
    help_text = parser.build_parser().format_help()

    assert "-h, --help" in help_text


def test_configured_help_alias_applies_to_subcommands(capsys) -> None:
    parser = Interfacy(backend="argparse", help_flags=("-h", "--help"))
    parser.add_command(alpha)
    parser.add_command(beta)

    result = parser.invoke(args=["alpha", "-h"])

    assert result is None
    assert "-h, --help" in capsys.readouterr().out


def test_optional_positional_usage_shows_optional_metavar() -> None:
    parser = Interfacy(
        backend="argparse",
    )
    parser.add_command(validate_config)

    help_text = parser.build_parser().format_help()

    assert "[CONFIG]" in help_text


def test_install_tab_completion_warns_when_argcomplete_is_missing(
    monkeypatch,
    capsys,
) -> None:
    parser = Interfacy(backend="argparse", tab_completion=True)
    parser.add_command(alpha)
    monkeypatch.setitem(sys.modules, "argcomplete", None)
    parser.build_parser()

    captured = capsys.readouterr()
    assert "argcomplete not installed" in captured.err


def test_schema_root_description_epilog_and_command_epilog_are_combined() -> None:
    command = Command(
        obj=Function(alpha),
        canonical_name="alpha",
        cli_name="alpha",
        aliases=(),
        raw_description="Alpha command.",
        raw_epilog="Command tail.",
    )
    schema = ParserSchema(
        raw_description="Root description.",
        raw_epilog="Root tail.",
        commands={"alpha": command},
        command_key="command",
        allow_args_from_file=True,
        pipe_targets=None,
    )

    cli = _compile_schema(schema).native_parser
    help_text = cli.format_help()

    assert "Root description." in help_text
    assert "Command tail." in help_text
    assert "Root tail." in help_text


def test_multi_command_schema_registers_aliases_and_executable_flags() -> None:
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
            ),
            "beta": Command(
                obj=Function(beta),
                canonical_name="beta",
                cli_name="beta",
                aliases=(),
                raw_description="Beta command.",
            ),
        },
        command_key="command",
        allow_args_from_file=True,
        pipe_targets=None,
        executable_flags=[ExecutableFlag(("--version",), lambda: "1.0", help="Show version.")],
    )

    cli = _compile_schema(schema).native_parser
    namespace = cli.parse_args(["a"])
    help_text = cli.format_help()

    assert namespace.command == "a"
    assert "--version" in help_text
    assert "alpha" in help_text
    assert "beta" in help_text

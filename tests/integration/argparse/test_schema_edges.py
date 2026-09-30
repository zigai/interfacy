from __future__ import annotations

import sys

import pytest

from interfacy import Interfacy, Param, params
from interfacy.exceptions import ConfigurationError
from interfacy.plugins import InterfacyPlugin


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
    class CommandEpilogPlugin(InterfacyPlugin):
        def transform_schema(self, context, schema):
            schema.commands["alpha"].raw_epilog = "Command tail."
            return schema

    parser = Interfacy(
        backend="argparse",
        description="Root description.",
        epilog="Root tail.",
        plugins=[CommandEpilogPlugin()],
    )
    parser.add_command(alpha, description="Alpha command.")

    help_text = parser.build_parser().format_help()

    assert "Root description." in help_text
    assert "Command tail." in help_text
    assert "Root tail." in help_text

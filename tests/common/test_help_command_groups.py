import re

import pytest

from interfacy import CommandGroup
from interfacy.appearance.layouts import ArgparseLayout
from interfacy.argparse_backend import Argparser
from interfacy.exceptions import ConfigurationError


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def cmd_status() -> None:
    """Show current status."""


def cmd_clone() -> None:
    """Clone a repository."""


def cmd_init() -> None:
    """Initialize a repository."""


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_root_help_groups_commands_before_ungrouped(parser, capsys) -> None:
    parser.add_command(cmd_status, name="status")
    parser.add_command(cmd_clone, name="clone", help_group="start a working area")
    parser.add_command(cmd_init, name="init", help_group="start a working area")

    result = parser.run(args=["--help"])
    assert isinstance(result, SystemExit)
    assert result.code == 0

    captured = capsys.readouterr()
    combined = _strip_ansi(captured.out + captured.err)
    lines = combined.splitlines()
    heading_idx = lines.index("start a working area")
    clone_idx = next(idx for idx, line in enumerate(lines) if line.strip().startswith("clone"))
    init_idx = next(idx for idx, line in enumerate(lines) if line.strip().startswith("init"))
    status_idx = next(idx for idx, line in enumerate(lines) if line.strip().startswith("status"))

    assert lines.count("start a working area") == 1
    assert sum(1 for line in lines if line.strip().startswith("clone")) == 1
    assert sum(1 for line in lines if line.strip().startswith("init")) == 1
    assert sum(1 for line in lines if line.strip().startswith("status")) == 1
    assert sum(1 for line in lines if line.strip().startswith("--help")) == 1
    assert "commands:" not in combined.lower()
    assert "start a working area:" not in combined
    assert heading_idx < clone_idx
    assert init_idx < status_idx


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_nested_help_groups_render_with_adaptive_layout(backend: str, capsys) -> None:
    if backend == "click":
        pytest.importorskip("click")
        from interfacy import ClickParser

        parser = ClickParser(
            help_layout=ArgparseLayout(),
            sys_exit_enabled=False,
            print_result=False,
        )
    else:
        parser = Argparser(
            help_layout=ArgparseLayout(),
            sys_exit_enabled=False,
            print_result=False,
        )

    ops = CommandGroup("ops")
    ops.add_command(cmd_status, name="status")
    ops.add_command(cmd_clone, name="clone", help_group="setup")
    ops.add_command(cmd_init, name="init", help_group="setup")
    parser.add_command(ops)

    result = parser.run(args=["ops", "--help"])
    assert isinstance(result, SystemExit)
    assert result.code == 0

    captured = capsys.readouterr()
    combined = _strip_ansi(captured.out + captured.err)
    lines = combined.splitlines()
    heading_idx = lines.index("setup")
    clone_idx = next(idx for idx, line in enumerate(lines) if line.strip().startswith("clone"))
    init_idx = next(idx for idx, line in enumerate(lines) if line.strip().startswith("init"))
    status_idx = next(idx for idx, line in enumerate(lines) if line.strip().startswith("status"))

    assert lines.count("setup") == 1
    assert sum(1 for line in lines if line.strip().startswith("clone")) == 1
    assert sum(1 for line in lines if line.strip().startswith("init")) == 1
    assert sum(1 for line in lines if line.strip().startswith("status")) == 1
    assert sum(1 for line in lines if line.strip().startswith("--help")) == 1
    assert "commands:" not in combined.lower()
    assert "setup" in combined
    assert "setup:" not in combined
    assert heading_idx < clone_idx
    assert init_idx < status_idx


def test_help_group_validation_rejects_invalid_values() -> None:
    parser = Argparser(sys_exit_enabled=False)

    with pytest.raises(ConfigurationError):
        parser.add_command(cmd_clone, help_group="")
    with pytest.raises(ConfigurationError):
        parser.add_command(cmd_clone, help_group="   ")
    with pytest.raises(ConfigurationError):
        parser.add_group(CommandGroup("ops"), help_group=object())  # type: ignore[arg-type]

    with pytest.raises(ConfigurationError):
        CommandGroup("tools").add_command(cmd_clone, help_group="")
    with pytest.raises(ConfigurationError):
        CommandGroup("tools").add_group(CommandGroup("sub"), help_group="   ")


def test_help_group_is_supported_on_all_registration_apis() -> None:
    parser = Argparser(sys_exit_enabled=False)

    parser.add_command(cmd_clone, name="clone-direct", help_group="top-level")

    @parser.command(name="decorated", help_group="decorated-group")
    def decorated() -> None:
        """Decorated command."""

    tools = CommandGroup("tools")
    tools.add_command(cmd_status, name="status", help_group="tooling")

    nested = CommandGroup("nested")
    nested.add_command(cmd_init, name="init")
    tools.add_group(nested, help_group="nested-ops")

    parser.add_group(tools, help_group="group-root")

    schema = parser.build_parser_schema()

    assert schema.commands["clone-direct"].help_group == "top-level"
    assert schema.commands["decorated"].help_group == "decorated-group"
    assert schema.commands["tools"].help_group == "group-root"

    tools_subcommands = schema.commands["tools"].subcommands or {}
    assert tools_subcommands["status"].help_group == "tooling"
    assert tools_subcommands["nested"].help_group == "nested-ops"

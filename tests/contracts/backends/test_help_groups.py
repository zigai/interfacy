import pytest

from interfacy import CommandGroup, Interfacy
from interfacy.exceptions import ConfigurationError
from interfacy.help.presets import ArgparseLayout, StandardLayout
from interfacy.help.terminal import strip_ansi


def cmd_status() -> None:
    """Show current status."""


def cmd_clone() -> None:
    """Clone a repository."""


def cmd_init() -> None:
    """Initialize a repository."""


def cmd_push() -> None:
    """Push changes."""


def cmd_pull() -> None:
    """Pull changes."""


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_root_help_groups_commands_before_ungrouped(parser, capsys) -> None:
    parser.add_command(cmd_status, name="status")
    parser.add_command(cmd_clone, name="clone", help_group="start a working area")
    parser.add_command(cmd_init, name="init", help_group="start a working area")

    result = parser.invoke(args=["--help"])
    assert result is None

    captured = capsys.readouterr()
    combined = strip_ansi(captured.out + captured.err)
    lines = combined.splitlines()
    heading_idx = lines.index("start a working area")
    clone_idx = next(idx for idx, line in enumerate(lines) if line.strip().startswith("clone"))
    init_idx = next(idx for idx, line in enumerate(lines) if line.strip().startswith("init"))
    status_idx = next(idx for idx, line in enumerate(lines) if line.strip().startswith("status"))

    assert lines.count("start a working area") == 1
    assert sum(1 for line in lines if line.strip().startswith("clone")) == 1
    assert sum(1 for line in lines if line.strip().startswith("init")) == 1
    assert sum(1 for line in lines if line.strip().startswith("status")) == 1
    assert sum(1 for line in lines if "--help" in line and "Show " in line) == 1
    assert "commands:" not in combined.lower()
    assert "start a working area:" not in combined
    assert heading_idx < clone_idx
    assert init_idx < status_idx


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_help_group_command_indent_is_configurable(parser, capsys) -> None:
    parser.apply_setup(help_layout=StandardLayout(command_indent=5))
    parser.add_command(cmd_clone, name="clone", help_group="setup")
    parser.add_command(cmd_status, name="status")

    result = parser.invoke(args=["--help"])
    assert result is None

    captured = capsys.readouterr()
    combined = strip_ansi(captured.out + captured.err)
    lines = combined.splitlines()

    assert any(line.startswith("     clone") for line in lines)


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_help_group_spacing_is_configurable(parser, capsys) -> None:
    parser.apply_setup(help_layout=StandardLayout(command_group_spacing=0))
    parser.add_command(cmd_clone, name="clone", help_group="setup")
    parser.add_command(cmd_push, name="push", help_group="sync")
    parser.add_command(cmd_pull, name="pull")

    result = parser.invoke(args=["--help"])
    assert result is None

    captured = capsys.readouterr()
    combined = strip_ansi(captured.out + captured.err)
    lines = combined.splitlines()
    clone_idx = next(idx for idx, line in enumerate(lines) if line.strip().startswith("clone"))
    sync_idx = lines.index("sync")
    push_idx = next(idx for idx, line in enumerate(lines) if line.strip().startswith("push"))
    pull_idx = next(idx for idx, line in enumerate(lines) if line.strip().startswith("pull"))

    assert lines[clone_idx + 1] == "sync"
    assert lines[push_idx + 1].lstrip().startswith("pull")
    assert sync_idx == clone_idx + 1
    assert pull_idx == push_idx + 1


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_nested_help_groups_render_with_adaptive_layout(backend: str, capsys) -> None:
    if backend == "click":
        pytest.importorskip("click")

        parser = Interfacy(
            backend="click",
            help_layout=ArgparseLayout(),
            print_result=False,
        )
    else:
        parser = Interfacy(
            backend="argparse",
            help_layout=ArgparseLayout(),
            print_result=False,
        )

    ops = CommandGroup("ops")
    ops.add_command(cmd_status, name="status")
    ops.add_command(cmd_clone, name="clone", help_group="setup")
    ops.add_command(cmd_init, name="init", help_group="setup")
    parser.add_command(ops)

    result = parser.invoke(args=["ops", "--help"])
    assert result is None

    captured = capsys.readouterr()
    combined = strip_ansi(captured.out + captured.err)
    lines = combined.splitlines()
    heading_idx = lines.index("setup")
    clone_idx = next(idx for idx, line in enumerate(lines) if line.strip().startswith("clone"))
    init_idx = next(idx for idx, line in enumerate(lines) if line.strip().startswith("init"))
    status_idx = next(idx for idx, line in enumerate(lines) if line.strip().startswith("status"))

    assert lines.count("setup") == 1
    assert sum(1 for line in lines if line.strip().startswith("clone")) == 1
    assert sum(1 for line in lines if line.strip().startswith("init")) == 1
    assert sum(1 for line in lines if line.strip().startswith("status")) == 1
    assert sum(1 for line in lines if "--help" in line and "Show " in line) == 1
    assert "commands:" not in combined.lower()
    assert "setup" in combined
    assert "setup:" not in combined
    assert heading_idx < clone_idx
    assert init_idx < status_idx


def test_help_group_validation_rejects_invalid_values() -> None:
    parser = Interfacy(
        backend="argparse",
    )

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
    parser = Interfacy(
        backend="argparse",
    )

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

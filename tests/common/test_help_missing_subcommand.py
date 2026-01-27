import pytest

from interfacy.group import CommandGroup


def test_no_args_prints_full_help(argparse_req_pos, capsys):
    argparse_req_pos.add_command(lambda: None, name="start", description="Start the thing")
    argparse_req_pos.add_command(lambda: None, name="down", description="Stop the thing")

    with pytest.raises(SystemExit):
        argparse_req_pos.run(args=[])

    captured = capsys.readouterr()
    combined = captured.out + captured.err

    assert "commands:" in combined
    assert "start" in combined
    assert "down" in combined
    assert "--help" in combined


def test_missing_nested_subcommand_prints_full_help(argparse_req_pos, capsys):
    workspace = CommandGroup("workspace")
    module = CommandGroup("module")
    workspace.add_group(module)
    module.add_command(lambda: None, name="attach", description="Attach to a container")

    argparse_req_pos.add_command(workspace)
    with pytest.raises(SystemExit):
        argparse_req_pos.run(args=["workspace", "module"])

    captured = capsys.readouterr()
    combined = captured.out + captured.err

    assert "commands:" in combined
    assert "attach" in combined

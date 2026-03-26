import pytest

from interfacy.group import CommandGroup


@pytest.mark.parametrize(
    ("parser", "expected_code"),
    [("argparse_req_pos", 2), ("click_req_pos", 0)],
    indirect=["parser"],
)
def test_no_args_prints_full_help(parser, expected_code, capsys):
    parser.add_command(lambda: None, name="start", description="Start the thing")
    parser.add_command(lambda: None, name="down", description="Stop the thing")

    result = parser.run(args=[])
    assert isinstance(result, SystemExit)
    assert result.code == expected_code

    captured = capsys.readouterr()
    combined = captured.out + captured.err

    assert "commands:" in combined
    assert "start" in combined
    assert "down" in combined
    assert "--help" in combined


@pytest.mark.parametrize(
    ("parser", "expected_code"),
    [("argparse_req_pos", 2), ("click_req_pos", 0)],
    indirect=["parser"],
)
def test_missing_nested_subcommand_prints_full_help(parser, expected_code, capsys):
    workspace = CommandGroup("workspace")
    module = CommandGroup("module")
    workspace.add_group(module)
    module.add_command(lambda: None, name="attach", description="Attach to a container")

    parser.add_command(workspace)
    result = parser.run(args=["workspace", "module"])
    assert isinstance(result, SystemExit)
    assert result.code == expected_code

    captured = capsys.readouterr()
    combined = captured.out + captured.err

    assert "commands:" in combined
    assert "attach" in combined

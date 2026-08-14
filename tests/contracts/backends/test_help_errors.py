import pytest

from interfacy.exceptions import UsageError
from interfacy.group import CommandGroup


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_no_args_reports_available_commands(parser):
    parser.add_command(lambda: None, name="start", description="Start the thing")
    parser.add_command(lambda: None, name="down", description="Stop the thing")

    with pytest.raises(UsageError) as exc_info:
        parser.invoke(args=[])

    combined = f"{exc_info.value}\n{exc_info.value.usage or ''}"
    assert "start" in combined
    assert "down" in combined


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_missing_nested_subcommand_reports_available_command(parser):
    workspace = CommandGroup("workspace")
    module = CommandGroup("module")
    workspace.add_group(module)
    module.add_command(lambda: None, name="attach", description="Attach to a container")

    parser.add_command(workspace)
    with pytest.raises(UsageError) as exc_info:
        parser.invoke(args=["workspace", "module"])

    combined = f"{exc_info.value}\n{exc_info.value.usage or ''}"
    assert "attach" in combined

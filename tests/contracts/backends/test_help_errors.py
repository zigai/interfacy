import pytest

from interfacy import Interfacy, Param
from interfacy.declarations.groups import CommandGroup
from interfacy.exceptions import UsageError
from interfacy.help import StandardLayout
from interfacy.naming import DefaultFlagStrategy


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


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_nested_unknown_command_uses_siblings_and_parent_help(parser, capsys, script_invocation):
    workspace = CommandGroup("workspace")
    module = CommandGroup("module")
    module.add_command(lambda: None, name="attach")
    module.add_command(lambda: None, name="detach")
    workspace.add_group(module)
    workspace.add_command(lambda: None, name="inspect")
    parser.add_command(workspace)

    with pytest.raises(SystemExit) as failure:
        parser.run(args=["workspace", "module", "xyz"])

    captured = capsys.readouterr()
    assert failure.value.code == 2
    assert captured.out == ""
    assert "Available commands: attach, detach" in captured.err
    assert "inspect" not in captured.err
    assert "Run 'tool workspace module --help'" in captured.err


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_missing_subcommand_prints_parent_help_without_parser_error(parser, capsys):
    workspace = CommandGroup("workspace")

    def attach() -> None:
        """Attach a module."""

    def detach() -> None:
        """Detach a module."""

    workspace.add_command(attach)
    workspace.add_command(detach)
    parser.add_command(workspace)

    with pytest.raises(SystemExit) as failure:
        parser.run(args=["workspace"])

    captured = capsys.readouterr()
    assert failure.value.code == 2
    assert captured.out == ""
    assert "Attach a module" in captured.err
    assert "Detach a module" in captured.err
    assert "the following arguments are required" not in captured.err
    assert "error:" not in captured.err


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_nested_missing_argument_reports_leaf_usage_and_diagnostic_path(parser, capsys):
    parser.apply_setup(flag_strategy=DefaultFlagStrategy(style="keyword_only"))

    def upload(*, workers: int) -> None:
        pytest.fail("Missing input must not execute")

    workspace = CommandGroup("workspace")
    workspace.add_command(upload)
    parser.add_command(workspace)

    with pytest.raises(UsageError) as failure:
        parser.invoke(args=["workspace", "upload"])

    assert failure.value.diagnostic.command_path == ("workspace", "upload")
    assert failure.value.diagnostic.argument == "--workers"
    assert "upload" in failure.value.usage
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_unknown_command_lists_canonical_names_once_with_aliases(backend, capsys):
    parser = Interfacy(backend=backend)
    parser.add_command(lambda: None, name="publish", aliases=["send"])
    parser.add_command(lambda: None, name="inspect")

    with pytest.raises(SystemExit):
        parser.run(args=["xyz"])

    output = capsys.readouterr().err
    assert "Available commands: publish, inspect" in output
    assert "send" not in output


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_unknown_option_can_suggest_an_ancestor_option(backend, capsys):
    class Service:
        def __init__(self, verbose: bool = False) -> None:
            self.verbose = verbose

        def status(self) -> None:
            pytest.fail("Suggestions must not execute")

    parser = Interfacy(backend=backend)
    with pytest.raises(SystemExit):
        parser.run(Service, args=["status", "--verbsoe"])

    assert "Did you mean '--verbose'?" in capsys.readouterr().err


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_diagnostic_usage_reuses_the_configured_help_layout(backend, capsys, script_invocation):
    def command(*, workers: int = 1) -> None:
        pytest.fail("Rejected input must not execute")

    parser = Interfacy(backend=backend, help_layout=StandardLayout(usage_prefix="Usage: "))
    parser.add_command(command, params={"workers": Param(short=False)})
    with pytest.raises(SystemExit):
        parser.run(args=["--workers", "bad"])

    output = capsys.readouterr().err
    assert "Usage: tool [--help] [--workers]" in output


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_missing_subcommand_in_implicit_class_shows_its_own_help(
    backend, capsys, script_invocation
):
    class Service:
        def publish(self, count: int) -> None:
            """Publish an artifact."""

        def inspect(self) -> None:
            """Inspect an artifact."""

    parser = Interfacy(backend=backend)
    parser.add_command(Service)
    with pytest.raises(SystemExit):
        parser.run(args=["publish"])

    output = capsys.readouterr().err
    assert "COUNT" in output
    assert "Run 'tool publish --help'" in output

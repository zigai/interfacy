import io
import sys
from typing import Any

import pytest

from interfacy import Interfacy, Param
from interfacy.declarations.groups import CommandGroup
from interfacy.exceptions import UsageError
from interfacy.help import DiagnosticResult, InterfacyLayout, StandardLayout
from interfacy.naming import DefaultFlagStrategy
from interfacy.plugins import InterfacyPlugin


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


def _workspace_app(backend: str, **settings: Any) -> Interfacy:
    def attach() -> None:
        """Attach a module."""

    def detach() -> None:
        """Detach a module."""

    def status() -> None:
        """Show the status."""

    module = CommandGroup("module")
    module.add_command(attach)
    module.add_command(detach)
    workspace = CommandGroup("workspace")
    workspace.add_group(module)
    parser = Interfacy(backend=backend, **settings)
    parser.add_command(status)
    parser.add_group(workspace)

    return parser


def _run_captured(
    parser: Interfacy, args: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[object, str, str]:
    with pytest.raises(SystemExit) as failure:
        parser.run(args=args)

    captured = capsys.readouterr()

    return failure.value.code, captured.out, captured.err


@pytest.mark.parametrize("backend", ["argparse", "click"])
@pytest.mark.parametrize("path", [["workspace"], ["workspace", "module"]])
def test_bare_group_prints_its_help_on_stdout(backend, path, capsys, script_invocation):
    help_code, help_out, help_err = _run_captured(
        _workspace_app(backend), [*path, "--help"], capsys
    )
    code, out, err = _run_captured(_workspace_app(backend), path, capsys)

    assert (help_code, help_err) == (0, "")
    assert (code, err) == (2, "")
    assert out.rstrip() == help_out.rstrip()
    assert "error" not in out


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_bare_group_in_machine_mode_reports_only_a_diagnostic(backend, capsys, script_invocation):
    class MachineDiagnostics(InterfacyPlugin):
        def render_diagnostic(self, context, content):
            return DiagnosticResult(f'{{"error": "{context.diagnostic.kind}"}}')

    parser = _workspace_app(backend)
    parser.add_plugin(MachineDiagnostics())

    code, out, err = _run_captured(parser, ["workspace"], capsys)

    assert code == 2
    assert out == ""
    assert err == '{"error": "missing_subcommand"}\n'


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_missing_argument_keeps_the_error_first_on_stderr(backend, capsys, script_invocation):
    def upload(path: str) -> None:
        pytest.fail("Missing input must not execute")

    parser = _workspace_app(backend)
    parser.add_command(upload)

    code, out, err = _run_captured(parser, ["upload"], capsys)

    assert code == 2
    assert out == ""
    assert err.startswith("error: missing required argument")


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
@pytest.mark.parametrize(
    ("option", "suggestions"),
    [("--count", []), ("--verbsoe", ["Did you mean '--verbose'?"])],
)
def test_unknown_option_suggestions_exclude_positional_names(backend, option, suggestions, capsys):
    def command(count: int, *, verbose: bool = False) -> None:
        pytest.fail("Rejected input must not execute")

    parser = Interfacy(backend=backend)
    with pytest.raises(SystemExit) as failure:
        parser.run(command, args=["1", option])

    captured = capsys.readouterr()
    assert failure.value.code == 2
    assert captured.out == ""
    assert f"unknown option {option!r}" in captured.err
    assert [line for line in captured.err.splitlines() if line.startswith("Did you mean")] == (
        suggestions
    )


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


class Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


@pytest.fixture
def color_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("NOCOLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")


@pytest.mark.parametrize("backend", ["argparse", "click"])
@pytest.mark.parametrize("args", [["workspace", "--help"], ["workspace"]])
@pytest.mark.parametrize(
    "switch", [None, ("NO_COLOR", "1"), ("NOCOLOR", "1"), ("TERM", "dumb")], ids=str
)
def test_help_color_follows_the_color_switches(
    backend, args, switch, color_env, monkeypatch, script_invocation
):
    if switch is not None:
        monkeypatch.setenv(*switch)
    terminal = Terminal()
    monkeypatch.setattr(sys, "stdout", terminal)
    monkeypatch.setattr(sys, "stderr", io.StringIO())

    with pytest.raises(SystemExit):
        _workspace_app(backend, help_layout=InterfacyLayout()).run(args=args)

    assert "Attach a module" not in terminal.getvalue()
    assert "module" in terminal.getvalue()
    assert ("\x1b[" in terminal.getvalue()) is (switch is None)


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_diagnostic_color_follows_stderr_not_stdout(
    backend, color_env, monkeypatch, script_invocation
):
    terminal = Terminal()
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    monkeypatch.setattr(sys, "stderr", terminal)

    with pytest.raises(SystemExit):
        _workspace_app(backend).run(args=["xyz"])

    assert "\x1b[" in terminal.getvalue()
    assert "unknown command" in terminal.getvalue()

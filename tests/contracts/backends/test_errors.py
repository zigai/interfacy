from typing import Any, Literal

import pytest
from pydantic import BaseModel, Field

from interfacy import (
    ConfigurationError,
    DiagnosticLayout,
    ExitCode,
    Interfacy,
    InterfacyError,
    UsageError,
)
from interfacy.naming import DefaultFlagStrategy
from interfacy.plugins import AfterParseContext, InterfacyPlugin


@pytest.fixture(params=["argparse", "click"])
def parser(request: pytest.FixtureRequest) -> Interfacy:
    parser_kwargs: dict[str, Any] = {
        "flag_strategy": DefaultFlagStrategy(style="required_positional"),
        "full_error_traceback": True,
        "help_layout": None,
        "print_result": False,
    }
    if request.param == "argparse":
        return Interfacy(backend="argparse", **parser_kwargs)

    pytest.importorskip("click")

    return Interfacy(backend="click", **parser_kwargs)


def test_invoke_returns_integer_command_data(parser: Interfacy) -> None:
    def count() -> int:
        return 7

    assert parser.invoke(count, args=[]) == 7


def test_invoke_raises_usage_error_without_rendering(
    parser: Interfacy,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def greet(name: str) -> str:
        return f"hello {name}"

    with pytest.raises(UsageError):
        parser.invoke(greet, args=[])

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_invoke_raises_configuration_error(parser: Interfacy) -> None:
    with pytest.raises(ConfigurationError, match="No commands were provided"):
        parser.invoke(args=[])


def test_invoke_propagates_command_exception(parser: Interfacy) -> None:
    def fail() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        parser.invoke(fail, args=[])


def test_invoke_propagates_interrupt_without_cli_callback(parser: Interfacy) -> None:

    def interrupt() -> None:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        parser.invoke(interrupt, args=[])


def test_invoke_propagates_explicit_system_exit(parser: Interfacy) -> None:
    def abort() -> None:
        raise SystemExit(7)

    with pytest.raises(SystemExit) as error:
        parser.invoke(abort, args=[])

    assert error.value.code == 7


def test_run_prints_integer_data_then_exits_successfully(
    parser: Interfacy,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser.apply_setup(print_result=True)

    def count() -> int:
        return 7

    with pytest.raises(SystemExit) as error:
        parser.run(count, args=[])

    assert error.value.code == ExitCode.SUCCESS
    assert capsys.readouterr().out == "7\n"


def test_run_maps_usage_failure_and_renders_usage(
    parser: Interfacy,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def greet(name: str) -> str:
        return f"hello {name}"

    with pytest.raises(SystemExit) as error:
        parser.run(greet, args=[])

    assert error.value.code == ExitCode.USAGE
    assert "usage:" in capsys.readouterr().err.lower()


def test_run_maps_configuration_failure(parser: Interfacy) -> None:
    with pytest.raises(SystemExit) as error:
        parser.run(args=[])

    assert error.value.code == ExitCode.CONFIGURATION


def test_run_maps_command_failure(parser: Interfacy) -> None:
    def fail() -> None:
        raise ValueError("boom")

    with pytest.raises(SystemExit) as error:
        parser.run(fail, args=[])

    assert error.value.code == ExitCode.COMMAND_FAILED


def test_run_maps_internal_framework_failure(parser: Interfacy) -> None:
    class BrokenPlugin(InterfacyPlugin):
        def after_parse(
            self,
            context: AfterParseContext,
            namespace: dict[str, Any],
        ) -> dict[str, Any]:
            del context, namespace
            raise InterfacyError("broken plugin")

    def command() -> None:
        return None

    parser.add_plugin(BrokenPlugin())
    with pytest.raises(SystemExit) as error:
        parser.run(command, args=[])

    assert error.value.code == ExitCode.INTERNAL


def test_run_maps_interrupt_and_calls_handler(parser: Interfacy) -> None:
    callbacks: list[str] = []
    runner = Interfacy(
        backend=parser.backend,
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        on_interrupt=lambda error: callbacks.append(type(error).__name__),
        silent_interrupt=True,
    )

    def interrupt() -> None:
        raise KeyboardInterrupt

    with pytest.raises(SystemExit) as error:
        runner.run(interrupt, args=[])

    assert error.value.code == ExitCode.INTERRUPTED
    assert callbacks == ["KeyboardInterrupt"]


def test_run_maps_help_to_success(parser: Interfacy) -> None:
    def command() -> None:
        return None

    with pytest.raises(SystemExit) as error:
        parser.run(command, args=["--help"])

    assert error.value.code == ExitCode.SUCCESS


def test_invoke_raises_usage_error_on_invalid_enum(parser: Interfacy) -> None:
    from enum import Enum

    class Color(Enum):
        RED = "red"
        BLUE = "blue"

    def set_color(c: Color) -> Color:
        return c

    with pytest.raises(UsageError):
        parser.invoke(set_color, args=["yellow"])


@pytest.mark.parametrize("full_traceback", [False, True])
def test_run_does_not_emit_rejected_model_input(
    parser: Interfacy,
    full_traceback: bool,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class Credentials(BaseModel):
        token: str = Field(min_length=32)

    def command(credentials: Credentials) -> str:
        return credentials.token

    parser.apply_setup(full_error_traceback=full_traceback)
    rejected = "synthetic-credential"

    with pytest.raises(SystemExit) as e:
        parser.run(command, args=["--credentials.token", rejected])

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "ValidationError" in captured.err
    assert rejected not in captured.err
    assert e.value.__cause__ is None
    assert e.value.__context__ is None


@pytest.mark.parametrize("full_traceback", [False, True])
def test_run_does_not_emit_command_exception_payloads_or_chains(
    parser: Interfacy,
    full_traceback: bool,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = "synthetic-response-body"

    def command() -> None:
        cause = ValueError(payload)
        raise RuntimeError(payload) from cause

    parser.apply_setup(full_error_traceback=full_traceback)

    with pytest.raises(SystemExit) as e:
        parser.run(command, args=[])

    captured = capsys.readouterr()
    assert "RuntimeError" in captured.err
    assert payload not in captured.err
    assert e.value.code == ExitCode.COMMAND_FAILED
    assert e.value.__cause__ is None
    assert e.value.__context__ is None


@pytest.mark.parametrize(
    ("args", "kind", "argument"),
    [
        ([], "missing_argument", "--workers"),
        (["--workers"], "missing_value", "--workers"),
        (["--workers", "private-input"], "invalid_type", "--workers"),
        (["--workers", "2", "--mode", "private-input"], "invalid_choice", "--mode"),
        (["--workers", "2", "--unknown"], "unknown_option", "--unknown"),
        (["--workers", "2", "private-input"], "unexpected_argument", None),
    ],
)
def test_parse_diagnostic_classifies_input_without_exposing_values(
    parser: Interfacy,
    args: list[str],
    kind: str,
    argument: str | None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser.apply_setup(flag_strategy=DefaultFlagStrategy(style="keyword_only"))

    def command(*, workers: int, mode: Literal["fast", "slow"] = "fast") -> None:
        pytest.fail("Rejected input must not execute the command")

    with pytest.raises(UsageError) as failure:
        parser.invoke(command, args=args)

    diagnostic = failure.value.diagnostic
    assert diagnostic is not None
    assert diagnostic.kind == kind
    assert diagnostic.argument == argument
    assert "private-input" not in str(failure.value)
    assert capsys.readouterr() == ("", "")


def test_positional_diagnostic_uses_the_displayed_metavar(
    parser: Interfacy,
) -> None:
    def command(count: int) -> None:
        pytest.fail("Rejected input must not execute")

    with pytest.raises(UsageError) as failure:
        parser.invoke(command, args=["private-input"])

    assert failure.value.diagnostic.argument == "COUNT"
    assert failure.value.diagnostic.kind == "invalid_type"
    assert "private-input" not in str(failure.value)


def test_unknown_command_is_concise_and_suggests_without_executing(
    parser: Interfacy,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    script_invocation: None,
) -> None:
    monkeypatch.setenv("NO_COLOR", "1")

    def command() -> None:
        pytest.fail("A spelling suggestion must not execute the command")

    parser.add_command(command, name="publish")
    parser.add_command(command, name="inspect")
    with pytest.raises(SystemExit) as failure:
        parser.run(args=["publsih"])

    captured = capsys.readouterr()
    assert failure.value.code == 2
    assert captured.out == ""
    assert captured.err == (
        "error: unknown command 'publsih'\n\n"
        "Did you mean 'publish'?\n"
        "Run 'tool --help' for usage.\n"
    )


def test_distant_unknown_command_lists_available_commands(
    parser: Interfacy,
    capsys: pytest.CaptureFixture[str],
    script_invocation: None,
) -> None:
    parser.add_command(lambda: None, name="publish")
    parser.add_command(lambda: None, name="inspect")

    with pytest.raises(SystemExit):
        parser.run(args=["xyz"])

    captured = capsys.readouterr()
    assert "Available commands: publish, inspect" in captured.err
    assert "Did you mean" not in captured.err
    assert "usage:" not in captured.err.lower()


@pytest.mark.parametrize("help_flags", [("--assist",), ("-?", "--assist")])
def test_error_hint_uses_only_configured_help_flags(
    parser: Interfacy,
    help_flags: tuple[str, ...],
    capsys: pytest.CaptureFixture[str],
    script_invocation: None,
) -> None:
    parser.apply_setup(help_flags=help_flags)
    parser.add_command(lambda: None, name="publish")
    parser.add_command(lambda: None, name="inspect")

    with pytest.raises(SystemExit):
        parser.run(args=["xyz"])

    output = capsys.readouterr().err
    assert "--help" not in output
    assert f"Run 'tool {help_flags[0]}'" in output


def test_unknown_option_does_not_echo_attached_value(
    parser: Interfacy,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        parser.run(lambda: None, args=["--unknown=private-input"])

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "unknown option '--unknown'" in captured.err
    assert "private-input" not in captured.err


def test_diagnostic_layout_changes_presentation_not_failure(
    parser: Interfacy,
    capsys: pytest.CaptureFixture[str],
    script_invocation: None,
) -> None:
    parser.apply_setup(
        diagnostic_layout=DiagnosticLayout(
            error_prefix="invalid:", sections=("message",), indent="  "
        )
    )
    parser.add_command(lambda: None, name="publish")
    parser.add_command(lambda: None, name="inspect")

    with pytest.raises(SystemExit) as failure:
        parser.run(args=["xyz"])

    assert failure.value.code == 2
    assert capsys.readouterr() == ("", "  invalid: unknown command 'xyz'\n")


@pytest.mark.parametrize("environment", [{"NO_COLOR": "1"}, {"TERM": "dumb"}, {}])
def test_redirected_diagnostics_are_plain_and_wrap_at_terminal_width(
    parser: Interfacy,
    environment: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("COLUMNS", "38")
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    parser.add_command(lambda: None, name="publish")
    parser.add_command(lambda: None, name="inspect")
    parser.add_command(lambda: None, name="synchronize")

    with pytest.raises(SystemExit):
        parser.run(args=["xyz"])

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "\x1b[" not in captured.err
    assert max(map(len, captured.err.splitlines())) <= 38

import asyncio
from typing import Literal

import pytest

from interfacy import CommandError, ExitCode, Interfacy
from interfacy.exceptions import (
    ConfigurationError,
    DuplicateCommandError,
    InterfacyError,
    InterfacyExit,
    InvalidCommandError,
    PipeInputError,
    ReservedFlagError,
    UnsupportedParameterTypeError,
    UsageError,
)
from interfacy.runtime.invocation import InvocationError


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize(
    ("failure", "expected_code"),
    [
        (CommandError("Fix the input"), ExitCode.COMMAND_FAILED),
        (PipeInputError("value", "missing input"), ExitCode.USAGE),
        (ConfigurationError("invalid configuration"), ExitCode.CONFIGURATION),
        (DuplicateCommandError("command"), ExitCode.CONFIGURATION),
        (InvalidCommandError("command"), ExitCode.CONFIGURATION),
        (ReservedFlagError("--flag"), ExitCode.CONFIGURATION),
        (UnsupportedParameterTypeError(complex), ExitCode.CONFIGURATION),
        (UsageError("execution failed"), ExitCode.INTERNAL),
        (InterfacyError("framework failed"), ExitCode.INTERNAL),
        (ValueError("command failed"), ExitCode.COMMAND_FAILED),
    ],
)
def test_execution_error_classification_preserves_original_exception(
    mode: Literal["sync", "async"],
    failure: Exception,
    expected_code: ExitCode,
) -> None:
    def command() -> None:
        raise failure

    async def async_command() -> None:
        raise failure

    parser = Interfacy()
    parser.add_command(command if mode == "sync" else async_command)
    core = parser._core
    runtime = core._runtime

    if mode == "sync":
        with pytest.raises(InvocationError) as e:
            runtime._invoke(core._parse_step((), []), core.execute)
    else:
        with pytest.raises(InvocationError) as e:
            asyncio.run(runtime._invoke_async(core._parse_step((), []), core.execute_async))

    assert e.value.code == expected_code
    assert e.value.error is failure
    assert e.value.__cause__ is failure


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize(
    "failure",
    [InterfacyExit(7), SystemExit(7), KeyboardInterrupt(), asyncio.CancelledError()],
)
def test_execution_propagates_exit_interrupt_and_cancellation(
    mode: Literal["sync", "async"],
    failure: BaseException,
) -> None:
    def command() -> None:
        raise failure

    async def async_command() -> None:
        raise failure

    parser = Interfacy()
    parser.add_command(command if mode == "sync" else async_command)
    core = parser._core
    runtime = core._runtime

    if mode == "sync":
        with pytest.raises(type(failure)) as e:
            runtime._invoke(core._parse_step((), []), core.execute)

        assert e.value is failure
    else:

        async def scenario() -> None:
            with pytest.raises(type(failure)) as e:
                await runtime._invoke_async(core._parse_step((), []), core.execute_async)

            assert e.value is failure

        asyncio.run(scenario())


class DomainError(CommandError):
    pass


@pytest.mark.parametrize("failure_type", [CommandError, DomainError, RuntimeError, InterfacyError])
@pytest.mark.parametrize("full_traceback", [False, True])
@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_run_only_displays_explicitly_user_facing_messages(
    failure_type: type[Exception],
    full_traceback: bool,
    backend: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    failure = failure_type("Stale receipt.\nRun provision apply.")
    failure.add_note("private note")

    def command() -> None:
        raise failure from ValueError("private cause")

    parser = Interfacy(backend=backend, full_error_traceback=full_traceback)
    with pytest.raises(SystemExit) as e:
        parser.run(command, args=[])

    assert e.value.code == (
        ExitCode.INTERNAL if failure_type is InterfacyError else ExitCode.COMMAND_FAILED
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert ("Stale receipt.\nRun provision apply." in captured.err) == issubclass(
        failure_type, CommandError
    )
    assert "private note" not in captured.err
    assert "private cause" not in captured.err
    assert ("Traceback" in captured.err) == full_traceback


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_embedded_user_facing_error_preserves_identity(
    mode: str, capsys: pytest.CaptureFixture[str]
) -> None:
    failure = DomainError("Correct the input")

    def command() -> None:
        raise failure

    async def async_command() -> None:
        raise failure

    if mode == "sync":
        with pytest.raises(DomainError) as e:
            Interfacy().invoke(command, args=[])
    else:
        with pytest.raises(DomainError) as e:
            asyncio.run(Interfacy().invoke_async(async_command, args=[]))

    assert e.value is failure
    assert capsys.readouterr() == ("", "")


def test_async_run_displays_user_facing_error(capsys: pytest.CaptureFixture[str]) -> None:
    async def command() -> None:
        raise DomainError("Correct the input")

    with pytest.raises(SystemExit) as e:
        Interfacy().run(command, args=[])

    assert e.value.code == ExitCode.COMMAND_FAILED
    assert capsys.readouterr() == ("", "Correct the input\n")


def test_executable_flag_user_facing_error_exits_with_command_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from interfacy import ExecutableFlag

    def diagnose() -> None:
        raise DomainError("Correct the configuration")

    def command() -> None:
        pass

    with pytest.raises(SystemExit) as e:
        Interfacy(executable_flags=[ExecutableFlag("--diagnose", diagnose)]).run(
            command, args=["--diagnose"]
        )

    assert e.value.code == ExitCode.COMMAND_FAILED
    assert capsys.readouterr() == ("", "Correct the configuration\n")

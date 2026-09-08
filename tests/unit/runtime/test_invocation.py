import asyncio
from typing import Literal

import pytest

from interfacy import ExitCode, Interfacy
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
    runtime = parser._engine._runtime

    if mode == "sync":
        with pytest.raises(InvocationError) as e:
            runtime._invoke((), [])
    else:
        with pytest.raises(InvocationError) as e:
            asyncio.run(runtime._invoke_async((), []))

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
    runtime = parser._engine._runtime

    if mode == "sync":
        with pytest.raises(type(failure)) as e:
            runtime._invoke((), [])

        assert e.value is failure
    else:

        async def scenario() -> None:
            with pytest.raises(type(failure)) as e:
                await runtime._invoke_async((), [])

            assert e.value is failure

        asyncio.run(scenario())

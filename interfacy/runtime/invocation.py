from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from inspect import isawaitable
from typing import Any, NoReturn

from interfacy.common.console import error
from interfacy.declarations.executable_flags import ExecutableAction
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
from interfacy.runtime.executable_flags import (
    ExecutableActionPending,
    execute_executable_flag,
    execute_executable_flag_async,
)
from interfacy.runtime.exit_codes import ExitCode
from interfacy.runtime.policy import RuntimePolicy
from interfacy.runtime.process import set_process_title_from_argv
from interfacy.schema.model import ParserSchema

CommandTarget = Callable[..., Any] | type | Any

_CONFIGURATION_ERRORS = (
    ConfigurationError,
    DuplicateCommandError,
    UnsupportedParameterTypeError,
    ReservedFlagError,
    InvalidCommandError,
)


@dataclass(frozen=True, slots=True)
class InvocationInput:
    """
    Parsed arguments together with the schema they were parsed against.

    ``supplied`` is ``namespace`` restricted to the values given on the command line, or
    ``None`` when that is unknown.
    """

    args: tuple[str, ...]
    namespace: dict[str, Any]
    schema: ParserSchema
    supplied: dict[str, Any] | None = None


ParseStep = Callable[[], InvocationInput]
ExecuteStep = Callable[[InvocationInput], Any]
AsyncExecuteStep = Callable[[InvocationInput], Awaitable[Any] | Any]


def resolve_args(args: Sequence[str] | None) -> tuple[str, ...]:
    """Return ``args``, or the process arguments when ``args`` is ``None``."""
    return tuple(sys.argv[1:] if args is None else args)


class InvocationError(Exception):
    def __init__(self, code: ExitCode, error: Exception) -> None:
        self.code = code
        self.error = error
        super().__init__(str(error))


def _execution_error_code(error: Exception) -> ExitCode:
    if isinstance(error, PipeInputError):
        return ExitCode.USAGE
    if isinstance(error, _CONFIGURATION_ERRORS):
        return ExitCode.CONFIGURATION
    if isinstance(error, InterfacyError):
        return ExitCode.INTERNAL
    return ExitCode.COMMAND_FAILED


def _parse_error_code(error: Exception) -> ExitCode:
    if isinstance(error, UsageError):
        return ExitCode.USAGE
    if isinstance(error, _CONFIGURATION_ERRORS):
        return ExitCode.CONFIGURATION
    return ExitCode.INTERNAL


class InvocationRuntime:
    """
    Run one parse-then-execute cycle under a ``RuntimePolicy``.

    Parse and execute failures are classified into exit codes; executable flags raised during
    parsing are completed in place of execution.
    """

    def __init__(self, policy: RuntimePolicy) -> None:
        self._policy = policy

    def invoke(self, parse: ParseStep, execute: ExecuteStep) -> Any:
        try:
            return self._invoke(parse, execute)
        except InterfacyExit:
            return None
        except InvocationError as e:
            raise e.error.with_traceback(e.error.__traceback__) from None

    async def invoke_async(self, parse: ParseStep, execute: AsyncExecuteStep) -> Any:
        try:
            return await self._invoke_async(parse, execute)
        except InterfacyExit:
            return None
        except InvocationError as e:
            raise e.error.with_traceback(e.error.__traceback__) from None

    def run(self, parse: ParseStep, execute: ExecuteStep) -> NoReturn:
        set_process_title_from_argv()
        try:
            result = self._invoke(parse, execute)
        except InterfacyExit as e:
            raise SystemExit(e.code) from None
        except (KeyboardInterrupt, asyncio.CancelledError) as e:
            self._policy.handle_interrupt(e)
            raise SystemExit(ExitCode.INTERRUPTED) from None
        except SystemExit:
            raise
        except InvocationError as e:
            failure = e.error
            if isinstance(failure, UsageError):
                if failure.usage:
                    error(failure.usage.rstrip())

                self._policy.log_error(str(failure))
            else:
                self._policy.log_exception(failure)

            raise SystemExit(e.code) from failure

        self._policy.display(result)

        raise SystemExit(ExitCode.SUCCESS)

    def _invoke(self, parse: ParseStep, execute: ExecuteStep) -> Any:
        try:
            invocation = self._parse(parse)
        except ExecutableActionPending as e:
            self._complete_action(e.action)

        return self._execute(execute, invocation)

    async def _invoke_async(self, parse: ParseStep, execute: AsyncExecuteStep) -> Any:
        try:
            invocation = self._parse(parse)
        except ExecutableActionPending as e:
            await self._complete_action_async(e.action)

        return await self._execute_async(execute, invocation)

    def _parse(self, parse: ParseStep) -> InvocationInput:
        try:
            return parse()
        except Exception as e:
            raise InvocationError(_parse_error_code(e), e) from e

    def _complete_action(self, action: ExecutableAction) -> NoReturn:
        try:
            code = execute_executable_flag(action.flag, display_result_fn=action.display_result_fn)
        except Exception as e:
            raise InvocationError(_parse_error_code(e), e) from e

        raise InterfacyExit(code)

    async def _complete_action_async(self, action: ExecutableAction) -> NoReturn:
        try:
            code = await execute_executable_flag_async(
                action.flag,
                display_result_fn=action.display_result_fn,
            )
        except Exception as e:
            raise InvocationError(_parse_error_code(e), e) from e

        raise InterfacyExit(code)

    def _execute(self, execute: ExecuteStep, invocation: InvocationInput) -> Any:
        try:
            return execute(invocation)
        except Exception as e:
            raise InvocationError(_execution_error_code(e), e) from e

    async def _execute_async(
        self,
        execute: AsyncExecuteStep,
        invocation: InvocationInput,
    ) -> Any:
        try:
            result = execute(invocation)
            if isawaitable(result):
                result = await result
        except Exception as e:
            raise InvocationError(_execution_error_code(e), e) from e
        else:
            return result


__all__ = [
    "CommandTarget",
    "InvocationError",
    "InvocationInput",
    "InvocationRuntime",
    "resolve_args",
]

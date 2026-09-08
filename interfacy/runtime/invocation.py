from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from inspect import isawaitable
from typing import Any, NoReturn, Protocol

from interfacy.console import error
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
from interfacy.executable_flag import (
    ExecutableAction,
    ExecutableActionPending,
    execute_executable_flag,
    execute_executable_flag_async,
)
from interfacy.runtime.exit_codes import ExitCode
from interfacy.runtime.policy import RuntimePolicy
from interfacy.runtime.process import set_process_title_from_argv

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
    args: tuple[str, ...]
    namespace: dict[str, Any]


class InvocationOperations(Protocol):
    def snapshot(self) -> object: ...

    def restore(self, snapshot: object) -> None: ...

    def register_inline(self, commands: Sequence[CommandTarget]) -> None: ...

    def reset_input(self) -> None: ...

    def resolve_args(self, args: Sequence[str] | None) -> tuple[str, ...]: ...

    def parse(self, args: tuple[str, ...]) -> InvocationInput: ...

    def execute(self, invocation: InvocationInput) -> Any: ...

    def execute_async(self, invocation: InvocationInput) -> Awaitable[Any] | Any: ...


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
    def __init__(self, operations: InvocationOperations, policy: RuntimePolicy) -> None:
        self._operations = operations
        self._policy = policy

    def invoke(
        self,
        commands: Sequence[CommandTarget],
        args: Sequence[str] | None = None,
    ) -> Any:
        try:
            return self._invoke(commands, args)
        except InterfacyExit:
            return None
        except InvocationError as e:
            raise e.error.with_traceback(e.error.__traceback__) from None

    async def invoke_async(
        self,
        commands: Sequence[CommandTarget],
        args: Sequence[str] | None = None,
    ) -> Any:
        try:
            return await self._invoke_async(commands, args)
        except InterfacyExit:
            return None
        except InvocationError as e:
            raise e.error.with_traceback(e.error.__traceback__) from None

    def run(
        self,
        commands: Sequence[CommandTarget],
        args: Sequence[str] | None = None,
    ) -> NoReturn:
        set_process_title_from_argv()
        try:
            result = self._invoke(commands, args)
        except InterfacyExit as e:
            raise SystemExit(e.code) from None
        except KeyboardInterrupt as e:
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

    def _invoke(
        self,
        commands: Sequence[CommandTarget],
        args: Sequence[str] | None,
    ) -> Any:
        snapshot = self._operations.snapshot() if commands else None
        try:
            try:
                invocation = self._parse(commands, args)
            except ExecutableActionPending as e:
                self._complete_action(e.action)

            return self._execute(invocation)
        finally:
            if snapshot is not None:
                self._operations.restore(snapshot)

    async def _invoke_async(
        self,
        commands: Sequence[CommandTarget],
        args: Sequence[str] | None,
    ) -> Any:
        snapshot = self._operations.snapshot() if commands else None
        try:
            try:
                invocation = self._parse(commands, args)
            except ExecutableActionPending as e:
                await self._complete_action_async(e.action)

            return await self._execute_async(invocation)
        finally:
            if snapshot is not None:
                self._operations.restore(snapshot)

    def _parse(
        self,
        commands: Sequence[CommandTarget],
        args: Sequence[str] | None,
    ) -> InvocationInput:
        try:
            self._operations.reset_input()
            self._operations.register_inline(commands)

            return self._operations.parse(self._operations.resolve_args(args))
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

    def _execute(self, invocation: InvocationInput) -> Any:
        try:
            return self._operations.execute(invocation)
        except Exception as e:
            raise InvocationError(_execution_error_code(e), e) from e

    async def _execute_async(self, invocation: InvocationInput) -> Any:
        try:
            result = self._operations.execute_async(invocation)
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
    "InvocationOperations",
    "InvocationRuntime",
]

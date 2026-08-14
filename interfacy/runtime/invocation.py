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
from interfacy.runtime.exit_codes import ExitCode
from interfacy.runtime.policy import RuntimePolicy
from interfacy.runtime.process import set_process_title_from_argv

CommandTarget = Callable[..., Any] | type | Any


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
            invocation = self._parse(commands, args)
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
            invocation = self._parse(commands, args)
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
        except (InterfacyExit, KeyboardInterrupt, SystemExit):
            raise
        except UsageError as e:
            raise InvocationError(ExitCode.USAGE, e) from e
        except (
            ConfigurationError,
            DuplicateCommandError,
            UnsupportedParameterTypeError,
            ReservedFlagError,
            InvalidCommandError,
        ) as e:
            raise InvocationError(ExitCode.CONFIGURATION, e) from e
        except Exception as e:
            raise InvocationError(ExitCode.INTERNAL, e) from e

    def _execute(self, invocation: InvocationInput) -> Any:
        try:
            return self._operations.execute(invocation)
        except (InterfacyExit, KeyboardInterrupt, SystemExit):
            raise
        except PipeInputError as e:
            raise InvocationError(ExitCode.USAGE, e) from e
        except ConfigurationError as e:
            raise InvocationError(ExitCode.CONFIGURATION, e) from e
        except InterfacyError as e:
            raise InvocationError(ExitCode.INTERNAL, e) from e
        except Exception as e:
            raise InvocationError(ExitCode.COMMAND_FAILED, e) from e

    async def _execute_async(self, invocation: InvocationInput) -> Any:
        try:
            result = self._operations.execute_async(invocation)
            if isawaitable(result):
                result = await result
        except (InterfacyExit, KeyboardInterrupt, SystemExit):
            raise
        except PipeInputError as e:
            raise InvocationError(ExitCode.USAGE, e) from e
        except ConfigurationError as e:
            raise InvocationError(ExitCode.CONFIGURATION, e) from e
        except InterfacyError as e:
            raise InvocationError(ExitCode.INTERNAL, e) from e
        except Exception as e:
            raise InvocationError(ExitCode.COMMAND_FAILED, e) from e
        else:
            return result


__all__ = [
    "CommandTarget",
    "InvocationError",
    "InvocationInput",
    "InvocationOperations",
    "InvocationRuntime",
]

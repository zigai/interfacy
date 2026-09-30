from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from interfacy.declarations.executable_flags import ExecutableAction, ExecutableFlag


class ExecutableActionPending(BaseException):
    """Transfer a detected flag from synchronous parsing to invocation execution."""

    def __init__(self, action: ExecutableAction) -> None:
        self.action = action
        super().__init__()


async def _await_handler_result(value: Awaitable[Any]) -> Any:
    return await value


def _resolve_handler_result(value: Any) -> Any:
    if not inspect.isawaitable(value):
        return value

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        if isinstance(value, asyncio.Future):
            loop = value.get_loop()
            if not loop.is_running():
                return loop.run_until_complete(value)
        else:
            return asyncio.run(_await_handler_result(value))

    if inspect.iscoroutine(value):
        value.close()

    raise RuntimeError(
        "A synchronous invocation cannot execute an async executable flag on a running event loop; "
        "use 'await invoke_async(...)'"
    )


def execute_executable_flag(
    flag: ExecutableFlag,
    *,
    display_result_fn: Callable[[Any], Any],
) -> int:
    """Execute a flag handler and display its result when configured."""
    result = _resolve_handler_result(flag.handler())
    if result is not None and flag.display_result:
        display_result_fn(result)

    return flag.exit_code


async def execute_executable_flag_async(
    flag: ExecutableFlag,
    *,
    display_result_fn: Callable[[Any], Any],
) -> int:
    """Complete a flag on the caller's event loop before displaying or exiting."""
    result = flag.handler()
    if inspect.isawaitable(result):
        result = await result

    if result is not None and flag.display_result:
        display_result_fn(result)

    return flag.exit_code


__all__ = ["ExecutableActionPending", "execute_executable_flag", "execute_executable_flag_async"]

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from interfacy.exceptions import ConfigurationError, ReservedFlagError

if TYPE_CHECKING:
    from interfacy.schema.schema import Argument


@dataclass
class ExecutableFlag:
    """Zero-argument executable CLI flag that short-circuits normal command execution."""

    flags: tuple[str, ...] | Sequence[str] | str
    handler: Callable[[], Any | None]
    help: str = ""
    display_result: bool = True
    exit_code: int = 0

    def __post_init__(self) -> None:
        self.flags = _normalize_flag_tuple(self.flags)
        if not callable(self.handler):
            raise ConfigurationError("ExecutableFlag.handler must be callable")
        if not isinstance(self.help, str):
            raise ConfigurationError("ExecutableFlag.help must be a string")
        if not isinstance(self.display_result, bool):
            raise ConfigurationError("ExecutableFlag.display_result must be a bool")
        if not isinstance(self.exit_code, int):
            raise ConfigurationError("ExecutableFlag.exit_code must be an int")
        if inspect.signature(self.handler).parameters:
            raise ConfigurationError("ExecutableFlag.handler must accept zero arguments")


@dataclass(frozen=True, slots=True)
class ExecutableAction:
    """A detected flag whose handler is completed by the invocation owner."""

    flag: ExecutableFlag
    display_result_fn: Callable[[Any], Any] = print


class ExecutableActionPending(BaseException):
    """Transfer a detected flag from synchronous parsing to invocation execution."""

    def __init__(self, action: ExecutableAction) -> None:
        self.action = action
        super().__init__()


def _normalize_flag_tuple(value: tuple[str, ...] | Sequence[str] | str) -> tuple[str, ...]:
    flags = (value,) if isinstance(value, str) else tuple(value)
    if not flags:
        raise ConfigurationError("ExecutableFlag.flags must contain at least one flag token")

    seen: set[str] = set()
    for flag in flags:
        if flag in seen:
            raise ReservedFlagError(flag)

        seen.add(flag)

        if not isinstance(flag, str) or not flag.startswith("-") or flag == "-":
            raise ConfigurationError(
                f"Executable flag tokens must start with '-' or '--': got {flag!r}"
            )

    return flags


def normalize_executable_flags(
    value: Sequence[ExecutableFlag] | None,
    *,
    value_name: str = "executable_flags",
) -> list[ExecutableFlag]:
    """Validate and copy a collection of executable flags."""
    if value is None:
        return []

    values = [value] if isinstance(value, ExecutableFlag) else list(value)

    normalized: list[ExecutableFlag] = []
    seen_tokens: set[str] = set()
    for flag in values:
        if not isinstance(flag, ExecutableFlag):
            raise ConfigurationError(f"{value_name} entries must be ExecutableFlag instances")

        for flag_name in flag.flags:
            if flag_name == "--help":
                raise ReservedFlagError(flag_name)

            if flag_name in seen_tokens:
                raise ReservedFlagError(flag_name)

            seen_tokens.add(flag_name)

        normalized.append(flag)

    return normalized


def executable_flag_tokens(flags: Sequence[ExecutableFlag]) -> set[str]:
    """Return the raw CLI tokens consumed by a collection of executable flags."""
    return {token for flag in flags for token in flag.flags}


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


def executable_flag_to_argument(flag: ExecutableFlag) -> Argument:
    """Return a synthetic schema argument for help rendering and option sorting."""
    from interfacy.parameters import BooleanMode
    from interfacy.schema.schema import (
        Argument,
        ArgumentDefault,
        ArgumentKind,
        BooleanBehavior,
        ValueCardinality,
        ValueShape,
    )

    primary = next((token for token in flag.flags if token.startswith("--")), flag.flags[0])
    name = primary.lstrip("-") or "flag"
    return Argument(
        name=name,
        display_name=name,
        kind=ArgumentKind.OPTION,
        value_shape=ValueShape.FLAG,
        flags=tuple(flag.flags),
        required=False,
        cardinality=ValueCardinality(0, 0, 0),
        argument_default=ArgumentDefault.present(value=False),
        help=flag.help,
        type=None,
        parser=None,
        boolean_behavior=BooleanBehavior(
            positive_flags=tuple(flag.flags),
            negative_flags=(),
            default=False,
            mode=BooleanMode.POSITIVE_ONLY,
        ),
    )


__all__ = [
    "ExecutableAction",
    "ExecutableFlag",
    "executable_flag_to_argument",
    "executable_flag_tokens",
    "execute_executable_flag",
    "execute_executable_flag_async",
    "normalize_executable_flags",
]

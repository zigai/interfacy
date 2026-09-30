from __future__ import annotations

import inspect
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from interfacy.exceptions import ConfigurationError, ReservedFlagError


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


__all__ = [
    "ExecutableAction",
    "ExecutableFlag",
    "executable_flag_tokens",
    "normalize_executable_flags",
]

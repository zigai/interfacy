from __future__ import annotations

import inspect
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from interfacy.exceptions import ConfigurationError, ReservedFlagError

if TYPE_CHECKING:
    from interfacy.schema.schema import Argument


@dataclass(frozen=True)
class ExecutableFlag:
    """Zero-argument executable CLI flag that short-circuits normal command execution."""

    flags: tuple[str, ...] | Sequence[str] | str
    handler: Callable[[], object | None]
    help: str = ""
    display_result: bool = True
    exit_code: int = 0

    def __post_init__(self) -> None:
        flags = _normalize_flag_tuple(self.flags)
        if not flags:
            raise ConfigurationError("ExecutableFlag.flags must contain at least one flag token")
        if len(set(flags)) != len(flags):
            duplicate = next(flag for flag in flags if flags.count(flag) > 1)
            raise ReservedFlagError(duplicate)
        for flag in flags:
            if not isinstance(flag, str) or not flag.startswith("-") or flag == "-":
                raise ConfigurationError(
                    f"Executable flag tokens must start with '-' or '--': got {flag!r}"
                )

        if not callable(self.handler):
            raise ConfigurationError("ExecutableFlag.handler must be callable")
        if not isinstance(self.help, str):
            raise ConfigurationError("ExecutableFlag.help must be a string")
        if not isinstance(self.display_result, bool):
            raise ConfigurationError("ExecutableFlag.display_result must be a bool")
        if not isinstance(self.exit_code, int):
            raise ConfigurationError("ExecutableFlag.exit_code must be an int")

        signature = inspect.signature(self.handler)
        if signature.parameters:
            raise ConfigurationError("ExecutableFlag.handler must accept zero arguments")

        object.__setattr__(self, "flags", flags)


def _normalize_flag_tuple(value: tuple[str, ...] | Sequence[str] | str) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    return tuple(value)


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


def execute_executable_flag(
    flag: ExecutableFlag,
    *,
    display_result_fn: Callable[[Any], Any],
) -> int:
    """Execute a flag handler and display its result when configured."""
    result = flag.handler()
    if result is not None and flag.display_result:
        display_result_fn(result)
    return flag.exit_code


def executable_flag_to_argument(flag: ExecutableFlag) -> Argument:
    """Return a synthetic schema argument for help rendering and option sorting."""
    from interfacy.schema.schema import Argument, ArgumentKind, BooleanBehavior, ValueShape

    primary = next((token for token in flag.flags if token.startswith("--")), flag.flags[0])
    name = primary.lstrip("-") or "flag"
    return Argument(
        name=name,
        display_name=name,
        kind=ArgumentKind.OPTION,
        value_shape=ValueShape.FLAG,
        flags=tuple(flag.flags),
        required=False,
        default=False,
        help=flag.help,
        type=None,
        parser=None,
        boolean_behavior=BooleanBehavior(
            supports_negative=False,
            negative_form=None,
            default=False,
        ),
    )


__all__ = [
    "ExecutableFlag",
    "executable_flag_to_argument",
    "executable_flag_tokens",
    "execute_executable_flag",
    "normalize_executable_flags",
]

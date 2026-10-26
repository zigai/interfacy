from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal, TypeAlias, TypeVar

from interfacy.exceptions import ConfigurationError

PARAMS_ATTR = "__interfacy_params__"

ParamsTarget: TypeAlias = Callable[..., Any] | type[Any]
ParamKind: TypeAlias = Literal["auto", "option", "positional"]
F = TypeVar("F", bound=ParamsTarget)


class BooleanMode(StrEnum):
    """Policy controlling which boolean flag polarities are exposed."""

    AUTO = "auto"
    DUAL = "dual"
    POSITIVE_ONLY = "positive_only"
    NEGATIVE_ONLY = "negative_only"


def _normalize_flag_tuple(
    value: Sequence[str] | str | None,
    *,
    field_name: str,
) -> tuple[str, ...] | None:
    if value is None:
        return None

    if isinstance(value, str):
        flags = (value,)
    elif isinstance(value, Sequence):
        flags = tuple(value)
    else:
        raise ConfigurationError(
            f"Param.{field_name} must be a flag string or sequence of flag strings"
        )

    if not flags:
        raise ConfigurationError(f"Param.{field_name} must contain at least one flag")

    normalized: list[str] = []
    seen: set[str] = set()

    for flag in flags:
        if not isinstance(flag, str):
            raise ConfigurationError(f"Param.{field_name} values must be strings")

        flag_value = flag.strip()
        if not flag_value or flag_value in {"-", "--"}:
            raise ConfigurationError(f"Param.{field_name} values must be non-empty flag strings")
        if not flag_value.startswith("-"):
            raise ConfigurationError(f"Param.{field_name} values must start with '-' or '--'")

        if flag_value in seen:
            raise ConfigurationError(f"Duplicate Param.{field_name} value: {flag_value}")

        normalized.append(flag_value)
        seen.add(flag_value)

    return tuple(normalized)


def _normalize_long_flag(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigurationError("Param.long must be a string")

    flag_value = value.strip()
    if not flag_value:
        raise ConfigurationError("Param.long must not be empty")

    if flag_value.startswith("-") and not flag_value.startswith("--"):
        raise ConfigurationError("Param.long must be a long flag such as '--name' or 'name'")

    if not flag_value.startswith("--"):
        flag_value = f"--{flag_value}"

    if flag_value == "--":
        raise ConfigurationError("Param.long must include a flag name")

    return flag_value


def _normalize_short_flag(value: str | bool | None) -> str | bool | None:
    if value is None or isinstance(value, bool):
        return value
    if not isinstance(value, str):
        raise ConfigurationError("Param.short must be a string, bool, or None")

    flag_value = value.strip()
    if not flag_value:
        raise ConfigurationError("Param.short must not be empty")

    if flag_value.startswith("--"):
        raise ConfigurationError("Param.short must be a short flag such as '-n' or 'n'")

    if not flag_value.startswith("-"):
        flag_value = f"-{flag_value}"

    if flag_value == "-":
        raise ConfigurationError("Param.short must include a flag name")

    return flag_value


def _normalize_boolean_mode(value: BooleanMode | str) -> BooleanMode:
    try:
        return BooleanMode(value)
    except ValueError:
        allowed = ", ".join(repr(mode.value) for mode in BooleanMode)
        raise ConfigurationError(f"Param.boolean_mode must be one of: {allowed}") from None


@dataclass
class Param:
    """Per-parameter CLI settings that keep the Python signature unchanged."""

    kind: ParamKind = "auto"
    flags: Sequence[str] | str | None = None
    negative_flags: Sequence[str] | str | None = None
    long: str | None = None
    short: str | bool | None = None
    help: str | None = None
    metavar: str | None = None
    boolean_mode: BooleanMode | str = BooleanMode.AUTO

    def __post_init__(self) -> None:
        if self.kind not in ("auto", "option", "positional"):
            raise ConfigurationError("Param.kind must be one of: 'auto', 'option', 'positional'")

        kind = self.kind
        flags = _normalize_flag_tuple(self.flags, field_name="flags")
        negative_flags = _normalize_flag_tuple(
            self.negative_flags,
            field_name="negative_flags",
        )
        long = _normalize_long_flag(self.long)
        short = _normalize_short_flag(self.short)
        boolean_mode = _normalize_boolean_mode(self.boolean_mode)

        if kind == "positional" and (
            flags is not None
            or negative_flags is not None
            or long is not None
            or short is not None
            or boolean_mode is not BooleanMode.AUTO
        ):
            raise ConfigurationError(
                "Param(kind='positional') cannot be combined with flag or boolean settings"
            )
        if flags is not None and (long is not None or short is not None):
            raise ConfigurationError(
                "Param.flags cannot be combined with Param.long or Param.short"
            )
        if self.help is not None and not isinstance(self.help, str):
            raise ConfigurationError("Param.help must be a string or None")
        if self.metavar is not None and not isinstance(self.metavar, str):
            raise ConfigurationError("Param.metavar must be a string or None")

        self.kind = kind
        self.flags = flags
        self.negative_flags = negative_flags
        self.long = long
        self.short = short
        self.boolean_mode = boolean_mode

    @property
    def has_flag_overrides(self) -> bool:
        """Whether this setting changes flag generation."""
        return self.flags is not None or self.long is not None or self.short not in (None, True)


ParamInput: TypeAlias = Param | Mapping[str, Any]
ParamMapInput: TypeAlias = Mapping[str, ParamInput]


def normalize_param(value: ParamInput, *, name: str) -> Param:
    """Normalize one Param declaration."""
    if isinstance(value, Param):
        return value
    if isinstance(value, Mapping):
        return Param(**dict(value))

    raise ConfigurationError(f"params[{name!r}] must be a Param or mapping")


def normalize_param_map(
    value: ParamMapInput | None,
) -> dict[str, Param]:
    """Normalize a mapping of parameter names to Param declarations."""
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ConfigurationError("params must be a mapping of parameter names to Param")

    normalized: dict[str, Param] = {}
    for name, setting in value.items():
        if not isinstance(name, str) or not name:
            raise ConfigurationError("params keys must be non-empty parameter names")

        normalized[name] = normalize_param(setting, name=name)

    return normalized


def get_params(target: ParamsTarget) -> dict[str, Param]:
    """Return Params declared directly on a callable or class."""
    raw = getattr(target, PARAMS_ATTR, None)
    return normalize_param_map(raw)


def merge_params(*settings: Mapping[str, Param] | None) -> dict[str, Param]:
    """Merge Param declarations from lowest to highest precedence."""
    merged: dict[str, Param] = {}
    for setting in settings:
        if setting:
            merged.update(setting)

    return merged


def params(**declared: ParamInput) -> Callable[[F], F]:
    """Decorate a callable or class with per-parameter CLI settings."""
    normalized = normalize_param_map(declared)

    def decorator(target: F) -> F:
        existing = get_params(target)
        setattr(target, PARAMS_ATTR, merge_params(existing, normalized))

        return target

    return decorator


__all__ = [
    "BooleanMode",
    "Param",
    "ParamKind",
    "ParamMapInput",
    "get_params",
    "merge_params",
    "normalize_param_map",
    "params",
]

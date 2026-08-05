from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias, TypeVar

from interfacy.exceptions import ConfigurationError

PARAMETER_SETTINGS_ATTR = "__interfacy_parameter_settings__"

ParameterSettingsTarget: TypeAlias = Callable[..., Any] | type[Any]
ParamKind: TypeAlias = Literal["auto", "option", "positional"]
F = TypeVar("F", bound=ParameterSettingsTarget)


def _normalize_flag_tuple(value: Sequence[str] | str | None) -> tuple[str, ...] | None:
    if value is None:
        return None

    if isinstance(value, str):
        flags = (value,)
    elif isinstance(value, Sequence):
        flags = tuple(value)
    else:
        raise ConfigurationError("Param.flags must be a flag string or sequence of flag strings")

    if not flags:
        raise ConfigurationError("Param.flags must contain at least one flag")

    normalized: list[str] = []
    seen: set[str] = set()

    for flag in flags:
        if not isinstance(flag, str):
            raise ConfigurationError("Param.flags values must be strings")

        flag_value = flag.strip()
        if not flag_value or flag_value in {"-", "--"}:
            raise ConfigurationError("Param.flags values must be non-empty flag strings")
        if not flag_value.startswith("-"):
            raise ConfigurationError("Param.flags values must start with '-' or '--'")

        if flag_value in seen:
            raise ConfigurationError(f"Duplicate Param.flags value: {flag_value}")

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


def _normalize_kind(value: str) -> ParamKind:
    match value:
        case "auto" | "option" | "positional":
            return value
        case _:
            raise ConfigurationError("Param.kind must be one of: 'auto', 'option', 'positional'")


@dataclass
class Param:
    """Per-parameter CLI settings that keep the Python signature unchanged."""

    kind: ParamKind = "auto"
    flags: Sequence[str] | str | None = None
    long: str | None = None
    short: str | bool | None = None
    help: str | None = None
    metavar: str | None = None

    def __post_init__(self) -> None:
        kind = _normalize_kind(self.kind)
        flags = _normalize_flag_tuple(self.flags)
        long = _normalize_long_flag(self.long)
        short = _normalize_short_flag(self.short)

        if kind == "positional" and (flags is not None or long is not None or short is not None):
            raise ConfigurationError(
                "Param(kind='positional') cannot be combined with Param.flags, "
                "Param.long, or Param.short"
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
        self.long = long
        self.short = short

    @property
    def has_flag_overrides(self) -> bool:
        """Whether this setting changes flag generation."""
        return self.flags is not None or self.long is not None or self.short not in (None, True)


ParamInput: TypeAlias = Param | Mapping[str, Any]
ParameterSettingsInput: TypeAlias = Mapping[str, ParamInput]


def normalize_param(value: ParamInput, *, name: str) -> Param:
    """Normalize one parameter setting declaration."""
    if isinstance(value, Param):
        return value
    if isinstance(value, Mapping):
        return Param(**dict(value))

    raise ConfigurationError(f"parameter_settings[{name!r}] must be a Param or mapping")


def normalize_parameter_settings(
    value: ParameterSettingsInput | None,
) -> dict[str, Param]:
    """Normalize a mapping of parameter names to Param declarations."""
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ConfigurationError("parameter_settings must be a mapping of parameter names to Param")

    normalized: dict[str, Param] = {}
    for name, setting in value.items():
        if not isinstance(name, str) or not name:
            raise ConfigurationError("parameter_settings keys must be non-empty parameter names")

        normalized[name] = normalize_param(setting, name=name)

    return normalized


def get_parameter_settings(target: ParameterSettingsTarget) -> dict[str, Param]:
    """Return settings declared directly on a callable or class."""
    raw = getattr(target, PARAMETER_SETTINGS_ATTR, None)
    return normalize_parameter_settings(raw)


def merge_parameter_settings(*settings: Mapping[str, Param] | None) -> dict[str, Param]:
    """Merge parameter settings from lowest to highest precedence."""
    merged: dict[str, Param] = {}
    for setting in settings:
        if setting:
            merged.update(setting)

    return merged


def params(**parameter_settings: ParamInput) -> Callable[[F], F]:
    """Decorate a callable or class with per-parameter CLI settings."""
    normalized = normalize_parameter_settings(parameter_settings)

    def decorator(target: F) -> F:
        existing = get_parameter_settings(target)
        setattr(target, PARAMETER_SETTINGS_ATTR, merge_parameter_settings(existing, normalized))

        return target

    return decorator


__all__ = [
    "Param",
    "ParamKind",
    "ParameterSettingsInput",
    "get_parameter_settings",
    "merge_parameter_settings",
    "normalize_parameter_settings",
    "params",
]

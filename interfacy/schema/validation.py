from typing import Any

from interfacy.exceptions import ConfigurationError


def validate_help_group(
    value: Any,
    *,
    value_name: str = "help_group",
    allow_none: bool = True,
) -> str | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{value_name} must be a non-empty string")

    return value


__all__ = ["validate_help_group"]

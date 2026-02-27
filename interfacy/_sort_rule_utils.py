from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

from interfacy.exceptions import ConfigurationError

_SortRule = TypeVar("_SortRule", bound=str)


def normalize_sort_rule_name(value: str) -> str:
    """Normalize a sort-rule token for case/format-insensitive matching."""
    return value.replace("-", "").replace("_", "").lower()


def resolve_sort_rules(
    value: object,
    *,
    value_name: str,
    allowed_values: Sequence[_SortRule],
    allow_none: bool = True,
    empty_means_none: bool = True,
) -> list[_SortRule] | None:
    """Validate and normalize a list of named sort rules."""
    if value is None:
        if allow_none:
            return None
        raise ConfigurationError(f"{value_name} must be a list")

    if not isinstance(value, list):
        raise ConfigurationError(f"{value_name} must be a list")

    lookup = {normalize_sort_rule_name(token): token for token in allowed_values}
    result: list[_SortRule] = []
    seen: set[_SortRule] = set()
    for item in value:
        if not isinstance(item, str):
            raise ConfigurationError(f"{value_name} values must be strings")
        token = lookup.get(normalize_sort_rule_name(item))
        if token is None:
            raise ConfigurationError(
                f"{value_name} contains invalid value: {item}. "
                "Allowed values: " + ", ".join(allowed_values)
            )
        if token in seen:
            continue
        seen.add(token)
        result.append(token)

    if not result and empty_means_none:
        return None
    return result

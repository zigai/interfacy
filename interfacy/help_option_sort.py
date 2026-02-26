from __future__ import annotations

from typing import Literal, cast

from interfacy.exceptions import ConfigurationError

HelpOptionSortRule = Literal[
    "required_first",
    "short_first",
    "value_first",
    "bool_last",
    "no_default_first",
    "choices_first",
    "name_length",
    "alias_count",
    "alphabetical",
]

HELP_OPTION_SORT_RULE_VALUES: tuple[HelpOptionSortRule, ...] = (
    "required_first",
    "short_first",
    "value_first",
    "bool_last",
    "no_default_first",
    "choices_first",
    "name_length",
    "alias_count",
    "alphabetical",
)

DEFAULT_HELP_OPTION_SORT_RULES: tuple[HelpOptionSortRule, ...] = (
    "required_first",
    "short_first",
    "bool_last",
    "alphabetical",
)


def _normalize_name(value: str) -> str:
    return value.replace("-", "").replace("_", "").lower()


_HELP_OPTION_SORT_LOOKUP = {_normalize_name(token): token for token in HELP_OPTION_SORT_RULE_VALUES}


def resolve_help_option_sort_rules(
    value: object,
    *,
    value_name: str = "help_option_sort",
    allow_none: bool = True,
    empty_means_none: bool = True,
) -> list[HelpOptionSortRule] | None:
    """Validate and normalize help option sort rules."""
    if value is None:
        if allow_none:
            return None
        raise ConfigurationError(f"{value_name} must be a list")

    if not isinstance(value, list):
        raise ConfigurationError(f"{value_name} must be a list")

    result: list[HelpOptionSortRule] = []
    seen: set[HelpOptionSortRule] = set()
    for item in value:
        if not isinstance(item, str):
            raise ConfigurationError(f"{value_name} values must be strings")
        token = _HELP_OPTION_SORT_LOOKUP.get(_normalize_name(item))
        if token is None:
            raise ConfigurationError(
                f"{value_name} contains invalid value: {item}. "
                "Allowed values: " + ", ".join(HELP_OPTION_SORT_RULE_VALUES)
            )
        normalized = cast(HelpOptionSortRule, token)
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)

    if not result and empty_means_none:
        return None
    return result


def default_help_option_sort_rules() -> list[HelpOptionSortRule]:
    """Return a mutable copy of the global default help option sort rules."""
    return list(DEFAULT_HELP_OPTION_SORT_RULES)


__all__ = [
    "DEFAULT_HELP_OPTION_SORT_RULES",
    "HELP_OPTION_SORT_RULE_VALUES",
    "HelpOptionSortRule",
    "default_help_option_sort_rules",
    "resolve_help_option_sort_rules",
]

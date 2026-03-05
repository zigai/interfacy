from __future__ import annotations

from typing import Literal

from interfacy.sort_rule_utils import resolve_sort_rules

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


def resolve_help_option_sort_rules(
    value: object,
    *,
    value_name: str = "help_option_sort",
    allow_none: bool = True,
    empty_means_none: bool = True,
) -> list[HelpOptionSortRule] | None:
    """Validate and normalize help option sort rules."""
    return resolve_sort_rules(
        value,
        value_name=value_name,
        allowed_values=HELP_OPTION_SORT_RULE_VALUES,
        allow_none=allow_none,
        empty_means_none=empty_means_none,
    )


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

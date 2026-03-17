from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, TypeVar

from interfacy.exceptions import ConfigurationError

T = TypeVar("T", bound=str)


def normalize_sort_rule_name(value: str) -> str:
    """Normalize a sort-rule token for case/format-insensitive matching."""
    return value.replace("-", "").replace("_", "").lower()


def resolve_sort_rules(
    value: object,
    *,
    value_name: str,
    allowed_values: Sequence[T],
    allow_none: bool = True,
    empty_means_none: bool = True,
) -> list[T] | None:
    """Validate and normalize a list of named sort rules."""
    if value is None:
        if allow_none:
            return None
        raise ConfigurationError(f"{value_name} must be a list")

    if not isinstance(value, list):
        raise ConfigurationError(f"{value_name} must be a list")

    lookup = {normalize_sort_rule_name(token): token for token in allowed_values}
    result: list[T] = []
    seen: set[T] = set()
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


HelpSubcommandSortRule = Literal[
    "insert_order",
    "alphabetical",
    "name_length_asc",
    "name_length_desc",
]

HELP_SUBCOMMAND_SORT_RULE_VALUES: tuple[HelpSubcommandSortRule, ...] = (
    "insert_order",
    "alphabetical",
    "name_length_asc",
    "name_length_desc",
)

DEFAULT_HELP_SUBCOMMAND_SORT_RULES: tuple[HelpSubcommandSortRule, ...] = ("insert_order",)


def resolve_help_subcommand_sort_rules(
    value: object,
    *,
    value_name: str = "help_subcommand_sort",
    allow_none: bool = True,
    empty_means_none: bool = True,
) -> list[HelpSubcommandSortRule] | None:
    """Validate and normalize help subcommand sort rules."""
    return resolve_sort_rules(
        value,
        value_name=value_name,
        allowed_values=HELP_SUBCOMMAND_SORT_RULE_VALUES,
        allow_none=allow_none,
        empty_means_none=empty_means_none,
    )


def default_help_subcommand_sort_rules() -> list[HelpSubcommandSortRule]:
    """Return a mutable copy of the global default help subcommand sort rules."""
    return list(DEFAULT_HELP_SUBCOMMAND_SORT_RULES)


__all__ = [
    "DEFAULT_HELP_OPTION_SORT_RULES",
    "DEFAULT_HELP_SUBCOMMAND_SORT_RULES",
    "HELP_OPTION_SORT_RULE_VALUES",
    "HELP_SUBCOMMAND_SORT_RULE_VALUES",
    "HelpOptionSortRule",
    "HelpSubcommandSortRule",
    "default_help_option_sort_rules",
    "default_help_subcommand_sort_rules",
    "normalize_sort_rule_name",
    "resolve_help_option_sort_rules",
    "resolve_help_subcommand_sort_rules",
    "resolve_sort_rules",
]

from __future__ import annotations

from typing import Literal

from interfacy._sort_rule_utils import resolve_sort_rules

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
    "DEFAULT_HELP_SUBCOMMAND_SORT_RULES",
    "HELP_SUBCOMMAND_SORT_RULE_VALUES",
    "HelpSubcommandSortRule",
    "default_help_subcommand_sort_rules",
    "resolve_help_subcommand_sort_rules",
]

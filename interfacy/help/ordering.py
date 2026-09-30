"""Apply help sort rules to command listings and option rows."""

from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

from interfacy.declarations.sorting import (
    DEFAULT_HELP_OPTION_SORT_RULES,
    DEFAULT_HELP_SUBCOMMAND_SORT_RULES,
    HelpOptionSortRule,
    HelpSubcommandSortRule,
    resolve_help_option_sort_rules,
    resolve_help_subcommand_sort_rules,
)

if TYPE_CHECKING:  # pragma: no cover
    from interfacy.help.layouts.base import HelpLayout
    from interfacy.schema import Argument, Command

NamedItemT = TypeVar("NamedItemT")

SUBCOMMAND_RULE_EXTRACTORS: dict[HelpSubcommandSortRule, Callable[[str], str | int]] = {
    "insert_order": lambda _name: 0,
    "alphabetical": str.lower,
    "name_length_asc": len,
    "name_length_desc": lambda name: -len(name),
}


def resolve_subcommand_sort_rules(
    layout: "HelpLayout",
    rules: list[HelpSubcommandSortRule] | None = None,
) -> list[HelpSubcommandSortRule]:
    """
    Return the command ordering rules that apply to a layout.

    Explicit rules win, then the layout's active rules, then its layout-level default, then
    the library default.

    Args:
        layout (HelpLayout): Layout holding the configured rules.
        rules (list[HelpSubcommandSortRule] | None): Explicit rules for this listing.
    """
    owner = layout.__class__.__name__
    if rules is not None:
        resolved_rules = resolve_help_subcommand_sort_rules(
            rules,
            value_name=f"{owner}.help_subcommand_sort_rules",
            allow_none=False,
        )
        return list(resolved_rules or ())

    active_rules = resolve_help_subcommand_sort_rules(
        layout.help_subcommand_sort_rules,
        value_name=f"{owner}.help_subcommand_sort_rules",
        allow_none=False,
    )
    if active_rules:
        return list(active_rules)

    layout_default_rules = resolve_help_subcommand_sort_rules(
        layout.help_subcommand_sort_default,
        value_name=f"{owner}.help_subcommand_sort_default",
    )
    if layout_default_rules:
        return list(layout_default_rules)

    return list(DEFAULT_HELP_SUBCOMMAND_SORT_RULES)


def order_named_items(
    layout: "HelpLayout",
    items: list[tuple[str, NamedItemT]],
    *,
    rules: list[HelpSubcommandSortRule] | None = None,
) -> list[NamedItemT]:
    """
    Sort named items by the layout's command ordering rules, keeping ties stable.

    Args:
        layout (HelpLayout): Layout holding the configured rules.
        items (list[tuple[str, NamedItemT]]): Items paired with their display names.
        rules (list[HelpSubcommandSortRule] | None): Explicit rules for this listing.
    """
    active_rules = resolve_subcommand_sort_rules(layout, rules)
    if not active_rules:
        return [item for _, item in items]

    rule_extractors = [SUBCOMMAND_RULE_EXTRACTORS[rule] for rule in active_rules]
    indexed_items = list(enumerate(items))
    indexed_items.sort(
        key=lambda item: (
            tuple(extractor(item[1][0]) for extractor in rule_extractors),
            item[0],
        ),
    )

    return [pair[1] for _, pair in indexed_items]


def order_command_list(
    layout: "HelpLayout",
    commands: list["Command"],
    *,
    rules: list[HelpSubcommandSortRule] | None = None,
) -> list["Command"]:
    """
    Sort commands by CLI name using the layout's command ordering rules.

    Args:
        layout (HelpLayout): Layout holding the configured rules.
        commands (list[Command]): Commands to sort.
        rules (list[HelpSubcommandSortRule] | None): Explicit rules for this listing.
    """
    named_commands = [(command.cli_name, command) for command in commands]
    return order_named_items(layout, named_commands, rules=rules)


def option_has_short_flag(arg: "Argument") -> bool:
    """Return whether an option exposes a short flag."""
    return any(flag.startswith("-") and not flag.startswith("--") for flag in arg.flags)


def option_sort_key(layout: "HelpLayout", arg: "Argument") -> str:
    """
    Return the lower-case name an option sorts by.

    Args:
        layout (HelpLayout): Layout that chooses the primary boolean flag.
        arg (Argument): Option to sort.
    """
    longs = [flag for flag in arg.flags if flag.startswith("--")]
    shorts = [flag for flag in arg.flags if flag.startswith("-") and not flag.startswith("--")]

    if layout._arg_is_bool(arg):
        primary_bool = layout.get_primary_boolean_flag_for_argument(arg)
        if primary_bool.startswith("--"):
            return primary_bool[2:].lower()
        if primary_bool.startswith("-"):
            return primary_bool[1:].lower()

    if longs:
        return longs[0][2:].lower()
    if shorts:
        return shorts[0][1:].lower()

    return (arg.display_name or arg.name).lower()


def resolve_option_sort_rules(
    layout: "HelpLayout",
    rules: list[HelpOptionSortRule] | None = None,
) -> list[HelpOptionSortRule]:
    """
    Return the option ordering rules that apply to a layout.

    Explicit rules win, then the layout's active rules, then its layout-level default, then
    the library default.

    Args:
        layout (HelpLayout): Layout holding the configured rules.
        rules (list[HelpOptionSortRule] | None): Explicit rules for this section.
    """
    owner = layout.__class__.__name__
    if rules is not None:
        resolved_rules = resolve_help_option_sort_rules(
            rules,
            value_name=f"{owner}.help_option_sort_rules",
            allow_none=False,
        )
        return list(resolved_rules or ())

    active_rules = resolve_help_option_sort_rules(
        layout.help_option_sort_rules,
        value_name=f"{owner}.help_option_sort_rules",
        allow_none=False,
    )
    if active_rules:
        return list(active_rules)

    layout_default_rules = resolve_help_option_sort_rules(
        layout.help_option_sort_default,
        value_name=f"{owner}.help_option_sort_default",
    )
    if layout_default_rules:
        return list(layout_default_rules)

    return list(DEFAULT_HELP_OPTION_SORT_RULES)


def option_rule_extractors(
    layout: "HelpLayout",
) -> dict[HelpOptionSortRule, Callable[["Argument"], str | int]]:
    """Return the sort-key extractor for each option ordering rule."""
    return {
        "required_first": lambda arg: 0 if arg.required else 1,
        "short_first": lambda arg: 0 if option_has_short_flag(arg) else 1,
        "value_first": lambda arg: 1 if layout._arg_is_bool(arg) else 0,
        "bool_last": lambda arg: 1 if layout._arg_is_bool(arg) else 0,
        "no_default_first": lambda arg: 0 if not layout._arg_has_default(arg) else 1,
        "choices_first": lambda arg: 0 if bool(arg.choices) else 1,
        "name_length": lambda arg: len(option_sort_key(layout, arg)),
        "alias_count": lambda arg: -len(arg.flags),
        "alphabetical": lambda arg: option_sort_key(layout, arg),
    }


def order_option_arguments(
    layout: "HelpLayout",
    options: list["Argument"],
    *,
    rules: list[HelpOptionSortRule] | None = None,
) -> list["Argument"]:
    """
    Sort options by the layout's option ordering rules, keeping ties stable.

    Args:
        layout (HelpLayout): Layout holding the configured rules.
        options (list[Argument]): Options to sort.
        rules (list[HelpOptionSortRule] | None): Explicit rules for this section.
    """
    active_rules = resolve_option_sort_rules(layout, rules)
    if not active_rules:
        return options

    extractors = option_rule_extractors(layout)
    rule_extractors = [extractors[rule] for rule in active_rules]
    indexed_options = list(enumerate(options))
    indexed_options.sort(
        key=lambda item: (
            tuple(extractor(item[1]) for extractor in rule_extractors),
            item[0],
        ),
    )

    return [option for _, option in indexed_options]


__all__ = [
    "SUBCOMMAND_RULE_EXTRACTORS",
    "option_has_short_flag",
    "option_rule_extractors",
    "option_sort_key",
    "order_command_list",
    "order_named_items",
    "order_option_arguments",
    "resolve_option_sort_rules",
    "resolve_subcommand_sort_rules",
]

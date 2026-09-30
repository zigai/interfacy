from __future__ import annotations

from dataclasses import replace
from typing import Any

from interfacy.declarations.options import OVERRIDE_NAMES, CommandOptions, CommandOverrides
from interfacy.declarations.sorting import (
    DEFAULT_HELP_OPTION_SORT_RULES,
    DEFAULT_HELP_SUBCOMMAND_SORT_RULES,
    HelpOptionSortRule,
    HelpSubcommandSortRule,
    resolve_help_option_sort_rules,
    resolve_help_subcommand_sort_rules,
)
from interfacy.schema.builder.context import EffectiveCommandSettings, SchemaBuildContext
from interfacy.schema.model import Command


def resolve_help_option_sort_value(value: Any, *, value_name: str) -> list[HelpOptionSortRule]:
    """
    Resolve configured option sort rules, falling back to the defaults.

    Args:
        value (Any): Configured rule value.
        value_name (str): Setting name used in error messages.
    """
    rules = resolve_help_option_sort_rules(value, value_name=value_name)
    if rules:
        return list(rules)

    return list(DEFAULT_HELP_OPTION_SORT_RULES)


def resolve_help_subcommand_sort_value(
    value: Any,
    *,
    value_name: str,
) -> list[HelpSubcommandSortRule]:
    """
    Resolve configured subcommand sort rules, falling back to the defaults.

    Args:
        value (Any): Configured rule value.
        value_name (str): Setting name used in error messages.
    """
    rules = resolve_help_subcommand_sort_rules(value, value_name=value_name)
    if rules:
        return list(rules)

    return list(DEFAULT_HELP_SUBCOMMAND_SORT_RULES)


def base_build_settings(context: SchemaBuildContext) -> EffectiveCommandSettings:
    """
    Return parser-level build settings from a schema build context.

    Args:
        context (SchemaBuildContext): Schema build context.
    """
    return EffectiveCommandSettings(
        include_inherited_methods=context.include_inherited_methods,
        include_protected_methods=context.include_protected_methods,
        include_private_methods=context.include_private_methods,
        include_staticmethods=context.include_staticmethods,
        include_classmethods=context.include_classmethods,
        method_skips=list(context.method_skips),
        expand_model_params=context.expand_model_params,
        model_expansion_max_depth=context.model_expansion_max_depth,
        abbreviation_scope=context.abbreviation_scope,
        help_option_sort=resolve_help_option_sort_value(
            context.help_option_sort,
            value_name="help_option_sort",
        ),
        help_subcommand_sort=resolve_help_subcommand_sort_value(
            context.help_subcommand_sort,
            value_name="help_subcommand_sort",
        ),
    )


def resolve_command_settings(
    base: EffectiveCommandSettings,
    overrides: CommandOverrides,
) -> EffectiveCommandSettings:
    """
    Apply the non-None command overrides to inherited settings.

    Args:
        base (EffectiveCommandSettings): Inherited settings.
        overrides (CommandOverrides): Per-command overrides.
    """
    updates: dict[str, Any] = {}
    for name in OVERRIDE_NAMES:
        value = getattr(overrides, name)
        if value is not None:
            updates[name] = list(value) if isinstance(value, (list, tuple)) else value

    return replace(base, **updates)


def resolve_effective_command_settings(
    context: SchemaBuildContext,
    parent: EffectiveCommandSettings | None,
    overrides: CommandOverrides,
) -> EffectiveCommandSettings:
    """
    Resolve a command's settings from its parent (or the parser) and its overrides.

    Args:
        context (SchemaBuildContext): Schema build context for parser-level settings.
        parent (EffectiveCommandSettings | None): Parent command settings.
        overrides (CommandOverrides): Per-command overrides.
    """
    base = parent or base_build_settings(context)
    return resolve_command_settings(base, overrides)


def attach_command_build_settings(
    command: Command,
    *,
    settings: EffectiveCommandSettings,
    options: CommandOptions,
) -> None:
    """
    Record a command's overrides and effective help sort rules.

    Args:
        command (Command): Command to update.
        settings (EffectiveCommandSettings): Resolved command settings.
        options (CommandOptions): Registration options whose overrides are recorded.
    """
    command.overrides = options.overrides
    command.help_option_sort_effective = list(settings.help_option_sort)
    command.help_subcommand_sort_effective = list(settings.help_subcommand_sort)


def registered_command_options(command: Command) -> CommandOptions:
    """
    Return the registration options recorded on a registered command.

    Args:
        command (Command): Registered command whose options are rebuilt.
    """
    return CommandOptions(
        **{name: getattr(command.overrides, name) for name in OVERRIDE_NAMES},
        help_group=command.help_group,
        executable_flags=command.executable_flags,
        parameter_settings=command.parameter_settings,
    )


def finalize_command_settings(
    command: Command,
    *,
    parent_option_rules: list[HelpOptionSortRule],
    parent_subcommand_rules: list[HelpSubcommandSortRule],
) -> None:
    """
    Recompute leaf status and inherited help sort rules for a command tree.

    Args:
        command (Command): Root of the command tree to update.
        parent_option_rules (list[HelpOptionSortRule]): Option rules inherited from the parent.
        parent_subcommand_rules (list[HelpSubcommandSortRule]): Subcommand rules inherited
            from the parent.
    """
    command.is_leaf = not bool(command.subcommands)
    if command.command_type == "group" and not command.subcommands:
        command.is_leaf = False

    command.help_option_sort_effective = list(
        command.overrides.help_option_sort
        if command.overrides.help_option_sort is not None
        else parent_option_rules
    )
    command.help_subcommand_sort_effective = list(
        command.overrides.help_subcommand_sort
        if command.overrides.help_subcommand_sort is not None
        else parent_subcommand_rules
    )

    if not command.subcommands:
        return

    for subcommand in command.subcommands.values():
        finalize_command_settings(
            subcommand,
            parent_option_rules=command.help_option_sort_effective,
            parent_subcommand_rules=command.help_subcommand_sort_effective,
        )


__all__ = [
    "attach_command_build_settings",
    "base_build_settings",
    "finalize_command_settings",
    "registered_command_options",
    "resolve_command_settings",
    "resolve_effective_command_settings",
    "resolve_help_option_sort_value",
    "resolve_help_subcommand_sort_value",
]

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from interfacy.appearance.help_sort import (
    HelpOptionSortRule,
    HelpSubcommandSortRule,
    resolve_help_option_sort_rules,
    resolve_help_subcommand_sort_rules,
)
from interfacy.exceptions import ConfigurationError

AbbreviationScope = Literal["top_level_options", "all_options"]
ABBREVIATION_SCOPE_VALUES: tuple[AbbreviationScope, ...] = ("top_level_options", "all_options")


def validate_abbreviation_scope(value: AbbreviationScope | None) -> AbbreviationScope | None:
    if value is None:
        return None
    if value not in ABBREVIATION_SCOPE_VALUES:
        raise ConfigurationError(
            "abbreviation_scope must be one of: " + ", ".join(ABBREVIATION_SCOPE_VALUES)
        )
    return value


def validate_help_option_sort(
    value: object,
) -> list[HelpOptionSortRule] | None:
    if value is None:
        return None
    return resolve_help_option_sort_rules(value, value_name="help_option_sort")


def validate_help_subcommand_sort(
    value: object,
) -> list[HelpSubcommandSortRule] | None:
    if value is None:
        return None
    return resolve_help_subcommand_sort_rules(value, value_name="help_subcommand_sort")


def validate_model_expansion_max_depth(value: int | None) -> int | None:
    if value is None:
        return None
    if value < 1:
        raise ConfigurationError("model_expansion_max_depth must be >= 1")
    return value


@dataclass
class CommandEntry:
    """Internal representation of a command added to a group."""

    obj: Callable[..., Any] | type | object
    name: str
    description: str | None
    aliases: tuple[str, ...]
    is_instance: bool
    include_inherited_methods: bool | None = None
    include_classmethods: bool | None = None
    expand_model_params: bool | None = None
    model_expansion_max_depth: int | None = None
    abbreviation_scope: AbbreviationScope | None = None
    help_option_sort: list[HelpOptionSortRule] | None = None
    help_subcommand_sort: list[HelpSubcommandSortRule] | None = None


class CommandGroup:
    """
    A command group for building nested CLI hierarchies.

    Supports manual construction of deeply nested command structures:
    - add_command(function) -> leaf command
    - add_command(class) -> subgroup with methods as commands
    - add_command(instance) -> subgroup with methods as commands (no __init__ args)
    - add_group(CommandGroup) -> nested subgroup
    """

    def __init__(
        self,
        name: str,
        description: str | None = None,
        aliases: tuple[str, ...] | list[str] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.aliases = tuple(aliases) if aliases else ()
        self._commands: dict[str, CommandEntry] = {}
        self._subgroups: dict[str, CommandGroup] = {}
        self._group_args_source: type | Callable[..., Any] | None = None

    def add_command(
        self,
        command: Callable[..., Any] | type | object,
        name: str | None = None,
        description: str | None = None,
        aliases: tuple[str, ...] | list[str] | None = None,
        include_inherited_methods: bool | None = None,
        include_classmethods: bool | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: AbbreviationScope | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
    ) -> CommandGroup:
        """
        Add a command to this group.

        Args:
            command: Function, class, or class instance to add.
            name: Override the command name (defaults to function/class name).
            description: Override the description.
            aliases: Alternative names for this command.
            include_inherited_methods: Override inherited-method inclusion.
            include_classmethods: Override classmethod inclusion.
            expand_model_params: Override model expansion toggle.
            model_expansion_max_depth: Override model expansion depth.
            abbreviation_scope: Override abbreviation scope.
            help_option_sort: Override help option sort rules.
            help_subcommand_sort: Override help subcommand sort rules.
        """
        resolved_abbreviation_scope = validate_abbreviation_scope(abbreviation_scope)
        resolved_help_option_sort = validate_help_option_sort(help_option_sort)
        resolved_help_subcommand_sort = validate_help_subcommand_sort(help_subcommand_sort)
        resolved_model_expansion_max_depth = validate_model_expansion_max_depth(
            model_expansion_max_depth
        )

        is_instance = False
        cmd_name: str

        if isinstance(command, type):
            cmd_name = name or command.__name__
        elif callable(command):
            callable_name = getattr(command, "__name__", None)
            fallback_name = (
                callable_name if isinstance(callable_name, str) else type(command).__name__
            )
            cmd_name = name or fallback_name
        else:
            is_instance = True
            cmd_name = name or type(command).__name__

        if description is None and hasattr(command, "__doc__") and command.__doc__:
            description = command.__doc__.split("\n")[0].strip()

        entry = CommandEntry(
            obj=command,
            name=cmd_name,
            description=description,
            aliases=tuple(aliases) if aliases else (),
            is_instance=is_instance,
            include_inherited_methods=include_inherited_methods,
            include_classmethods=include_classmethods,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=resolved_model_expansion_max_depth,
            abbreviation_scope=resolved_abbreviation_scope,
            help_option_sort=list(resolved_help_option_sort) if resolved_help_option_sort else None,
            help_subcommand_sort=list(resolved_help_subcommand_sort)
            if resolved_help_subcommand_sort
            else None,
        )
        self._commands[cmd_name] = entry
        return self

    def add_group(
        self,
        group: CommandGroup,
        name: str | None = None,
    ) -> CommandGroup:
        """
        Add a nested subgroup.

        Args:
            group: The CommandGroup to add as a subgroup.
            name: Override the subgroup name.
        """
        group_name = name or group.name
        self._subgroups[group_name] = group
        return self

    def with_args(self, source: type | Callable[..., Any]) -> CommandGroup:
        """
        Set group-level arguments from a class __init__ or function signature.

        Args:
            source: A class (uses __init__ params) or callable (uses signature).
        """
        self._group_args_source = source
        return self

    @property
    def commands(self) -> dict[str, CommandEntry]:
        """Return a copy of the commands dictionary."""
        return dict(self._commands)

    @property
    def subgroups(self) -> dict[str, CommandGroup]:
        """Return a copy of the subgroups dictionary."""
        return dict(self._subgroups)

    @property
    def has_subgroups(self) -> bool:
        """Whether this group contains nested subgroups."""
        return len(self._subgroups) > 0

    @property
    def has_commands(self) -> bool:
        """Whether this group contains direct commands."""
        return len(self._commands) > 0

    @property
    def is_empty(self) -> bool:
        """Whether this group has no commands or subgroups."""
        return not self.has_commands and not self.has_subgroups

    def __repr__(self) -> str:
        return (
            f"CommandGroup(name={self.name!r}, "
            f"commands={list(self._commands.keys())}, "
            f"subgroups={list(self._subgroups.keys())})"
        )


__all__ = ["CommandEntry", "CommandGroup"]

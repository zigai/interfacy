from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from inspect import isroutine
from typing import Any, Literal

from interfacy.appearance.help_sort import (
    HelpOptionSortRule,
    HelpSubcommandSortRule,
    resolve_help_option_sort_rules,
    resolve_help_subcommand_sort_rules,
)
from interfacy.exceptions import ConfigurationError, DuplicateCommandError
from interfacy.executable_flag import ExecutableFlag, normalize_executable_flags
from interfacy.util import validate_help_group

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
    help_group: str | None = None
    executable_flags: list[ExecutableFlag] | None = None


@dataclass
class SubgroupEntry:
    """Internal representation of a subgroup added to a group."""

    group: CommandGroup
    help_group: str | None = None
    executable_flags: list[ExecutableFlag] | None = None


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
        self._subgroups: dict[str, SubgroupEntry] = {}
        self._group_args_source: type | Callable[..., Any] | None = None

    def _ensure_unique_child_name(self, name: str) -> None:
        if name in self._commands or name in self._subgroups:
            raise DuplicateCommandError(name)

    @staticmethod
    def _is_instance_command(command: Callable[..., Any] | type | object) -> bool:
        if isinstance(command, type):
            return False
        if not callable(command):
            return True
        if isroutine(command):
            return False

        for attr_name in dir(type(command)):
            if attr_name.startswith("_") or attr_name == "__call__":
                continue
            attr = getattr(type(command), attr_name, None)
            if callable(attr):
                return True
        return False

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
        help_group: str | None = None,
        executable_flags: list[ExecutableFlag] | None = None,
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
            help_group: Optional help-only group heading for this command in help listings.
            executable_flags: Zero-argument executable flags registered on this command node.
        """
        resolved_abbreviation_scope = validate_abbreviation_scope(abbreviation_scope)
        resolved_help_option_sort = validate_help_option_sort(help_option_sort)
        resolved_help_subcommand_sort = validate_help_subcommand_sort(help_subcommand_sort)
        resolved_model_expansion_max_depth = validate_model_expansion_max_depth(
            model_expansion_max_depth
        )
        resolved_help_group = validate_help_group(help_group)
        resolved_executable_flags = normalize_executable_flags(
            executable_flags,
            value_name="executable_flags",
        )

        is_instance = self._is_instance_command(command)
        cmd_name: str

        if isinstance(command, type):
            cmd_name = name or command.__name__
        elif not is_instance and callable(command):
            callable_name = getattr(command, "__name__", None)
            fallback_name = (
                callable_name if isinstance(callable_name, str) else type(command).__name__
            )
            cmd_name = name or fallback_name
        else:
            cmd_name = name or type(command).__name__

        self._ensure_unique_child_name(cmd_name)

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
            help_group=resolved_help_group,
            executable_flags=list(resolved_executable_flags) if resolved_executable_flags else None,
        )
        self._commands[cmd_name] = entry
        return self

    def add_group(
        self,
        group: CommandGroup,
        name: str | None = None,
        help_group: str | None = None,
        executable_flags: list[ExecutableFlag] | None = None,
    ) -> CommandGroup:
        """
        Add a nested subgroup.

        Args:
            group: The CommandGroup to add as a subgroup.
            name: Override the subgroup name.
            help_group: Optional help-only group heading for this subgroup command.
            executable_flags: Zero-argument executable flags registered on the subgroup node.
        """
        group_name = name or group.name
        self._ensure_unique_child_name(group_name)
        resolved_help_group = validate_help_group(help_group)
        resolved_executable_flags = normalize_executable_flags(
            executable_flags,
            value_name="executable_flags",
        )
        self._subgroups[group_name] = SubgroupEntry(
            group=group,
            help_group=resolved_help_group,
            executable_flags=(
                list(resolved_executable_flags) if resolved_executable_flags else None
            ),
        )
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
        return {name: entry.group for name, entry in self._subgroups.items()}

    @property
    def subgroup_entries(self) -> dict[str, SubgroupEntry]:
        """Return subgroup entries with associated metadata."""
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


__all__ = ["CommandEntry", "CommandGroup", "SubgroupEntry"]

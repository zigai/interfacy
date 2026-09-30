from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from objinspect import Class, Function, Method, inspect

from interfacy.declarations.groups import CommandEntry, CommandGroup
from interfacy.declarations.options import DEFAULT_COMMAND_OPTIONS, CommandOptions
from interfacy.declarations.params import Param, merge_parameter_settings
from interfacy.exceptions import DuplicateCommandError, InvalidCommandError
from interfacy.introspection.annotations import resolve_objinspect_annotations
from interfacy.schema.builder.arguments import ArgumentBuilder
from interfacy.schema.builder.classes import ClassCommandBuilder, class_parameter_settings
from interfacy.schema.builder.commands import CommandBuilder, callable_parameter_settings
from interfacy.schema.builder.context import EffectiveCommandSettings, SchemaBuildContext
from interfacy.schema.builder.settings import (
    attach_command_build_settings,
    resolve_effective_command_settings,
)
from interfacy.schema.model import Argument, Command
from interfacy.schema.validation import validate_initializer_positionals


def group_args_source(group: CommandGroup) -> type | Callable[..., Any] | None:
    """
    Return the class or callable whose signature defines a group's own arguments.

    Args:
        group (CommandGroup): Command group.
    """
    source = getattr(group, "group_args_source", None)
    if source is not None:
        return source

    return getattr(group, "_group_args_source", None)


def register_child_names(taken_names: set[str], candidates: tuple[str, ...]) -> None:
    """
    Reserve a child command's translated name and aliases within its parent group.

    Args:
        taken_names (set[str]): Names already used by sibling commands, updated in place.
        candidates (tuple[str, ...]): Translated name followed by translated aliases.

    Raises:
        DuplicateCommandError: A candidate repeats or is already used by a sibling.
    """
    seen_candidates: set[str] = set()
    for candidate in candidates:
        if candidate in seen_candidates:
            raise DuplicateCommandError(candidate)

        seen_candidates.add(candidate)

    for candidate in candidates:
        if candidate in taken_names:
            raise DuplicateCommandError(candidate)

    taken_names.update(candidates)


@dataclass
class GroupBuilder:
    """Convert manually assembled command groups into schema command trees."""

    context: SchemaBuildContext
    arguments: ArgumentBuilder
    commands: CommandBuilder
    classes: ClassCommandBuilder

    def group_command(
        self,
        group: CommandGroup,
        parent_path: tuple[str, ...] = (),
        canonical_name: str | None = None,
        *,
        parent_settings: EffectiveCommandSettings | None = None,
        options: CommandOptions = DEFAULT_COMMAND_OPTIONS,
    ) -> Command:
        """
        Build a group command with nested subgroups and command entries.

        Args:
            group (CommandGroup): Group to convert.
            parent_path (tuple[str, ...]): Command path of the parent group.
            canonical_name (str | None): Canonical name; translated group name when omitted.
            parent_settings (EffectiveCommandSettings | None): Parent effective settings.
            options (CommandOptions): Per-command registration options.

        Raises:
            DuplicateCommandError: Two children share a translated name or alias.
        """
        settings = resolve_effective_command_settings(self.context, parent_settings, options)
        cli_name = canonical_name or self.commands.translate_command_name(group.name)
        current_path = (*parent_path, cli_name)

        initializer: list[Argument] = []
        source = group_args_source(group)
        if source is not None:
            initializer = self.args_from_source(
                source,
                settings=settings,
                parameter_settings=options.parameter_settings,
            )
        resolved_executable_flags = list(options.executable_flags)
        self.commands.validate_executable_flags(resolved_executable_flags, initializer)

        subcommands: dict[str, Command] = {}
        translated_child_names: set[str] = set()

        for name, subgroup_entry in group.subgroup_entries.items():
            sub_cli_name = self._register_child(
                translated_child_names,
                name,
                subgroup_entry.group.aliases,
            )
            subcommands[sub_cli_name] = self.group_command(
                subgroup_entry.group,
                current_path,
                parent_settings=settings,
                options=subgroup_entry.options,
            )

        for name, entry in group.commands.items():
            sub_cli_name = self._register_child(translated_child_names, name, entry.aliases)
            subcommands[sub_cli_name] = self.entry_command(
                entry,
                current_path,
                parent_settings=settings,
            )

        validate_initializer_positionals(initializer, owner=cli_name, subcommands=subcommands)

        command = Command(
            obj=None,
            canonical_name=cli_name,
            cli_name=cli_name,
            aliases=group.aliases,
            raw_description=group.description,
            help_group=options.help_group,
            parameters=[],
            initializer=initializer,
            subcommands=subcommands or None,
            executable_flags=resolved_executable_flags,
            raw_epilog=None,
            command_type="group",
            is_leaf=False,
            parent_path=parent_path,
            metadata={},
            parameter_settings=dict(options.parameter_settings),
        )
        attach_command_build_settings(command, settings=settings, options=options)

        return command

    def args_from_source(
        self,
        source: type | Callable[..., Any],
        *,
        settings: EffectiveCommandSettings,
        parameter_settings: Mapping[str, Param] | None = None,
    ) -> list[Argument]:
        """
        Build group arguments from a class `__init__` or a callable signature.

        Args:
            source (type | Callable[..., Any]): Class or callable defining the arguments.
            settings (EffectiveCommandSettings): Effective group settings.
            parameter_settings (Mapping[str, Param] | None): Per-parameter settings.
        """
        obj = inspect(source, init=True)
        resolve_objinspect_annotations(obj)
        taken_flags = [*self.context.reserved_flags]

        if isinstance(obj, Class) and obj.init_method:
            return self.arguments.from_parameters(
                obj.init_method.params,
                taken_flags,
                set(),
                settings=settings,
                parameter_settings=merge_parameter_settings(
                    class_parameter_settings(obj),
                    parameter_settings,
                ),
            )

        if isinstance(obj, Function):
            return self.arguments.from_parameters(
                obj.params,
                taken_flags,
                set(),
                settings=settings,
                parameter_settings=merge_parameter_settings(
                    callable_parameter_settings(obj),
                    parameter_settings,
                ),
            )

        return []

    def entry_command(
        self,
        entry: CommandEntry,
        parent_path: tuple[str, ...],
        *,
        parent_settings: EffectiveCommandSettings,
    ) -> Command:
        """
        Build the command for a group entry holding a function, class, or instance.

        Args:
            entry (CommandEntry): Group entry to convert.
            parent_path (tuple[str, ...]): Command path of the parent group.
            parent_settings (EffectiveCommandSettings): Effective settings of the group.

        Raises:
            InvalidCommandError: The entry object is not a supported command target.
        """
        settings = resolve_effective_command_settings(self.context, parent_settings, entry.options)
        if entry.is_instance:
            return self.classes.instance_command(entry, parent_path, settings=settings)

        if isinstance(entry.obj, type):
            return self.classes.class_tree_command(entry, parent_path, settings=settings)

        obj = inspect(entry.obj)
        resolve_objinspect_annotations(obj)

        if isinstance(obj, (Function, Method)):
            return self.commands.function_command(
                obj,
                canonical_name=self.commands.translate_command_name(entry.name),
                description=entry.description,
                aliases=entry.aliases,
                pipe_config=entry.pipe_targets,
                settings=settings,
                options=entry.options,
            )

        raise InvalidCommandError(entry.name)

    def _register_child(
        self,
        taken_names: set[str],
        name: str,
        aliases: tuple[str, ...],
    ) -> str:
        cli_name = self.commands.translate_command_name(name)
        translated_aliases = tuple(self.commands.translate_command_name(alias) for alias in aliases)
        register_child_names(taken_names, (cli_name, *translated_aliases))

        return cli_name


__all__ = ["GroupBuilder", "group_args_source", "register_child_names"]

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from objinspect import Class, Function, Method

from interfacy.declarations.groups import CommandGroup
from interfacy.declarations.options import DEFAULT_COMMAND_OPTIONS, CommandOptions
from interfacy.exceptions import InvalidCommandError
from interfacy.introspection.annotations import resolve_objinspect_annotations
from interfacy.schema.builder.arguments import ArgumentBuilder
from interfacy.schema.builder.classes import ClassCommandBuilder
from interfacy.schema.builder.commands import CommandBuilder
from interfacy.schema.builder.context import EffectiveCommandSettings, SchemaBuildContext
from interfacy.schema.builder.groups import GroupBuilder
from interfacy.schema.builder.settings import (
    finalize_command_settings,
    registered_command_options,
    resolve_effective_command_settings,
)
from interfacy.schema.model import Command, ParserSchema
from interfacy.schema.validation import validate_parser_schema, validate_schema_executable_flags


@dataclass
class ParserSchemaBuilder:
    """
    Build semantic parser schemas from an explicit neutral context.

    Attributes:
        context (SchemaBuildContext): Source and policy snapshot for the build.
        arguments (ArgumentBuilder): Converts parameters into arguments.
        commands (CommandBuilder): Converts functions and methods into commands.
        classes (ClassCommandBuilder): Converts classes and instances into commands.
        groups (GroupBuilder): Converts command groups into command trees.
    """

    context: SchemaBuildContext
    arguments: ArgumentBuilder = field(init=False)
    commands: CommandBuilder = field(init=False)
    classes: ClassCommandBuilder = field(init=False)
    groups: GroupBuilder = field(init=False)

    def __post_init__(self) -> None:
        self.arguments = ArgumentBuilder(self.context)
        self.commands = CommandBuilder(self.context, self.arguments)
        self.classes = ClassCommandBuilder(self.context, self.arguments, self.commands)
        self.groups = GroupBuilder(self.context, self.arguments, self.commands, self.classes)

    def build_unfinalized(self) -> ParserSchema:
        """Build raw semantic schema data without plugins or finalization."""
        commands: dict[str, Command] = {}
        for canonical_name, command in self.context.commands.items():
            commands[canonical_name] = self._rebuild_registered_command(command)

        return ParserSchema(
            raw_description=self.context.description,
            raw_epilog=self.context.epilog,
            commands=commands,
            command_key=self.context.command_key,
            allow_args_from_file=self.context.allow_args_from_file,
            pipe_targets=self.context.pipe_targets_default,
            metadata=dict(self.context.metadata),
            executable_flags=list(self.context.executable_flags),
            help_option_sort_effective=list(self.context.help_option_sort_effective),
            help_subcommand_sort_effective=list(self.context.help_subcommand_sort_effective),
            help_flags=self.context.help_flags,
        )

    def build(self) -> ParserSchema:
        """Build and finalize a schema when no transform phase is required."""
        return self.finalize(self.build_unfinalized())

    def finalize(self, schema: ParserSchema) -> ParserSchema:
        """
        Finalize and validate a transformed semantic schema.

        Args:
            schema (ParserSchema): Schema returned by the transform phase.
        """
        validate_parser_schema(schema)
        root_option_rules = list(
            schema.help_option_sort_effective or self.context.help_option_sort_effective
        )
        root_subcommand_rules = list(
            schema.help_subcommand_sort_effective or self.context.help_subcommand_sort_effective
        )
        for command in schema.commands.values():
            finalize_command_settings(
                command,
                parent_option_rules=root_option_rules,
                parent_subcommand_rules=root_subcommand_rules,
            )

        validate_schema_executable_flags(schema, help_flags=self.context.help_flags)

        return schema

    def build_command_spec_for(
        self,
        obj: Class | Function | Method,
        *,
        canonical_name: str,
        description: str | None = None,
        aliases: tuple[str, ...] = (),
        parent_settings: EffectiveCommandSettings | None = None,
        options: CommandOptions = DEFAULT_COMMAND_OPTIONS,
    ) -> Command:
        """
        Build a Command schema for a callable or class.

        Args:
            obj (Class | Function | Method): Inspected target to convert.
            canonical_name (str): Canonical command name.
            description (str | None): Optional description override.
            aliases (tuple[str, ...]): Alternate command names.
            parent_settings (EffectiveCommandSettings | None): Parent effective settings.
            options (CommandOptions): Per-command registration options.
        """
        settings = resolve_effective_command_settings(self.context, parent_settings, options)
        resolve_objinspect_annotations(obj)
        kwargs: dict[str, Any] = {
            "canonical_name": canonical_name,
            "description": description,
            "aliases": aliases,
            "settings": settings,
            "options": options,
        }
        if isinstance(obj, Method):
            return self.commands.method_command(obj, **kwargs)
        if isinstance(obj, Function):
            return self.commands.function_command(obj, **kwargs)
        if isinstance(obj, Class):
            return self.classes.class_command(obj, **kwargs)

        raise InvalidCommandError(obj)

    def build_from_group(
        self,
        group: CommandGroup,
        parent_path: tuple[str, ...] = (),
        canonical_name: str | None = None,
        parent_settings: EffectiveCommandSettings | None = None,
        options: CommandOptions = DEFAULT_COMMAND_OPTIONS,
    ) -> Command:
        """Build Command schema from a CommandGroup (manual construction)."""
        return self.groups.group_command(
            group,
            parent_path,
            canonical_name,
            parent_settings=parent_settings,
            options=options,
        )

    def _rebuild_registered_command(self, command: Command) -> Command:
        options = registered_command_options(command)
        if command.group_source is not None:
            rebuilt_group = self.build_from_group(
                command.group_source,
                canonical_name=command.canonical_name,
                options=options,
            )
            rebuilt_group.aliases = command.aliases
            rebuilt_group.raw_description = command.raw_description
            rebuilt_group.group_source = command.group_source

            return rebuilt_group

        if command.command_type in ("group", "instance") or (
            not command.is_leaf and command.obj is None
        ):
            return command
        if command.obj is None:
            raise InvalidCommandError(command.canonical_name)

        return self.build_command_spec_for(
            command.obj,
            canonical_name=command.canonical_name,
            description=command.raw_description,
            aliases=command.aliases,
            options=options,
        )


__all__ = ["ParserSchemaBuilder"]

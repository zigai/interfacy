from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from objinspect import Class, Parameter, inspect

from interfacy.declarations.groups import CommandEntry
from interfacy.declarations.options import DEFAULT_COMMAND_OPTIONS, CommandOptions
from interfacy.declarations.params import Param, get_parameter_settings, merge_parameter_settings
from interfacy.declarations.pipes import PipeTargets
from interfacy.introspection.annotations import resolve_objinspect_annotations
from interfacy.models import parse_docstring_args
from interfacy.schema.builder.arguments import ArgumentBuilder
from interfacy.schema.builder.commands import CommandBuilder, resolve_cli_name
from interfacy.schema.builder.context import EffectiveCommandSettings, SchemaBuildContext
from interfacy.schema.builder.settings import attach_command_build_settings, base_build_settings
from interfacy.schema.model import Argument, Command
from interfacy.schema.validation import validate_initializer_positionals


def class_parameter_settings(class_info: Class) -> dict[str, Param]:
    """
    Return parameter settings declared on a class merged with those on its `__init__`.

    Args:
        class_info (Class): Inspected class or instance.
    """
    class_target = class_info.cls if isinstance(class_info.cls, type) else type(class_info.cls)
    class_settings = get_parameter_settings(class_target)
    init_settings = (
        get_parameter_settings(class_info.init_method.func)
        if class_info.init_method is not None
        else {}
    )

    return merge_parameter_settings(class_settings, init_settings)


def pipe_config_for_params(
    pipe_config: PipeTargets | None,
    params: Sequence[Parameter],
) -> PipeTargets | None:
    """
    Narrow a pipe configuration to the targets present in a parameter list.

    Args:
        pipe_config (PipeTargets | None): Pipe configuration to narrow.
        params (Sequence[Parameter]): Parameters that may receive piped input.
    """
    if pipe_config is None:
        return None

    param_names = {param.name for param in params}
    targets = tuple(target for target in pipe_config.targets if target in param_names)
    if not targets:
        return None
    if targets == pipe_config.targets:
        return pipe_config

    return PipeTargets(
        targets=targets,
        delimiter=pipe_config.delimiter,
        priority=pipe_config.priority,
        allow_partial=pipe_config.allow_partial,
    )


@dataclass
class ClassCommandBuilder:
    """Convert classes and instances into commands whose methods are subcommands."""

    context: SchemaBuildContext
    arguments: ArgumentBuilder
    commands: CommandBuilder

    def class_command(
        self,
        cls: Class,
        *,
        canonical_name: str | None = None,
        description: str | None = None,
        aliases: tuple[str, ...] = (),
        settings: EffectiveCommandSettings | None = None,
        options: CommandOptions = DEFAULT_COMMAND_OPTIONS,
    ) -> Command:
        """
        Build a class command whose methods become subcommands.

        Args:
            cls (Class): Inspected class.
            canonical_name (str | None): Canonical command name.
            description (str | None): Description override.
            aliases (tuple[str, ...]): Alternate command names.
            settings (EffectiveCommandSettings | None): Effective command settings.
            options (CommandOptions): Per-command registration options.
        """
        resolved_settings = settings or base_build_settings(self.context)
        initializer: list[Argument] = []
        class_pipe_config = self.commands.resolve_pipe_config(
            canonical_name, cls.name, aliases, None
        )
        init_pipe_config = (
            self.commands.resolve_pipe_config(canonical_name, cls.name, aliases, "__init__")
            or class_pipe_config
        )
        effective_parameter_settings = merge_parameter_settings(
            class_parameter_settings(cls),
            options.parameter_settings,
        )

        if cls.has_init and not cls.is_initialized:
            initializer = self.arguments.from_parameters(
                cls.get_method("__init__").params,
                self._initializer_taken_flags(),
                init_pipe_config.targeted_parameters() if init_pipe_config else set(),
                settings=resolved_settings,
                parameter_settings=effective_parameter_settings,
                descriptions=parse_docstring_args(cls.cls.__doc__),
            )

        subcommands: dict[str, Command] = {}
        method_options = CommandOptions(parameter_settings=options.parameter_settings)

        for method in cls.methods:
            if method.name in resolved_settings.method_skips:
                continue

            method_cli_name = self.commands.translate_command_name(method.name)
            sub_pipe_config = None
            if canonical_name is not None:
                sub_pipe_config = (
                    self.commands.resolve_pipe_config(
                        canonical_name, cls.name, aliases, method_cli_name
                    )
                    or self.commands.resolve_pipe_config(
                        canonical_name, cls.name, aliases, method.name
                    )
                    or class_pipe_config
                )

            subcommands[method_cli_name] = self.commands.function_command(
                method,
                cli_name_override=method_cli_name,
                pipe_config=sub_pipe_config,
                settings=resolved_settings,
                options=method_options,
            )

        raw_description = description or (cls.description if cls.has_docstring else None)
        cli_name = resolve_cli_name(None, canonical_name, cls.name)
        validate_initializer_positionals(initializer, owner=cli_name, subcommands=subcommands)
        resolved_executable_flags = list(options.executable_flags)
        self.commands.validate_executable_flags(resolved_executable_flags, initializer)

        command = Command(
            obj=cls,
            canonical_name=cli_name,
            cli_name=cli_name,
            aliases=aliases,
            raw_description=raw_description,
            help_group=options.help_group,
            parameters=[],
            initializer=initializer,
            subcommands=subcommands,
            raw_epilog=None,
            pipe_targets=class_pipe_config,
            executable_flags=resolved_executable_flags,
            command_type="class",
            is_leaf=False,
            parameter_settings=dict(effective_parameter_settings),
        )
        attach_command_build_settings(
            command,
            settings=resolved_settings,
            options=options,
        )

        return command

    def instance_command(
        self,
        entry: CommandEntry,
        parent_path: tuple[str, ...],
        *,
        settings: EffectiveCommandSettings,
    ) -> Command:
        """
        Build a command from a stored instance; its methods become subcommands.

        Args:
            entry (CommandEntry): Group entry holding the instance.
            parent_path (tuple[str, ...]): Command path of the parent group.
            settings (EffectiveCommandSettings): Effective command settings.
        """
        instance = entry.obj
        options = entry.options
        cls = self._inspect_class(type(instance), settings=settings, init=False)

        subcommands: dict[str, Command] = {}
        method_options = CommandOptions(parameter_settings=options.parameter_settings)
        for method in cls.methods:
            if method.name in settings.method_skips:
                continue

            method_cli_name = self.commands.translate_command_name(method.name)
            subcommands[method_cli_name] = self.commands.function_command(
                method,
                cli_name_override=method_cli_name,
                pipe_config=entry.pipe_targets,
                settings=settings,
                options=method_options,
            )

        cli_name = self.commands.translate_command_name(entry.name)
        raw_description = entry.description or (cls.description if cls.has_docstring else None)
        resolved_executable_flags = list(options.executable_flags)
        self.commands.validate_executable_flags(resolved_executable_flags, [])

        command = Command(
            obj=cls,
            canonical_name=cli_name,
            cli_name=cli_name,
            aliases=entry.aliases,
            raw_description=raw_description,
            help_group=options.help_group,
            parameters=[],
            initializer=[],
            subcommands=subcommands or None,
            executable_flags=resolved_executable_flags,
            raw_epilog=None,
            pipe_targets=entry.pipe_targets,
            command_type="instance",
            is_leaf=False,
            is_instance=True,
            parent_path=parent_path,
            stored_instance=instance,
            metadata={},
            parameter_settings=dict(options.parameter_settings),
        )
        attach_command_build_settings(
            command,
            settings=settings,
            options=options,
        )

        return command

    def class_tree_command(
        self,
        entry: CommandEntry,
        parent_path: tuple[str, ...],
        *,
        settings: EffectiveCommandSettings,
    ) -> Command:
        """
        Build a class command whose methods and nested classes become subcommands.

        Args:
            entry (CommandEntry): Group entry holding the class.
            parent_path (tuple[str, ...]): Command path of the parent group.
            settings (EffectiveCommandSettings): Effective command settings.
        """
        cls = self._inspect_class(entry.obj, settings=settings, init=True)
        options = entry.options
        cli_name = self.commands.translate_command_name(entry.name)
        current_path = (*parent_path, cli_name)

        initializer: list[Argument] = []
        init_params = (
            cls.get_method("__init__").params if cls.has_init and not cls.is_initialized else []
        )
        init_pipe_config = pipe_config_for_params(entry.pipe_targets, init_params)
        effective_parameter_settings = merge_parameter_settings(
            class_parameter_settings(cls),
            options.parameter_settings,
        )

        if init_params:
            initializer = self.arguments.from_parameters(
                init_params,
                self._initializer_taken_flags(),
                init_pipe_config.targeted_parameters() if init_pipe_config else set(),
                settings=settings,
                parameter_settings=effective_parameter_settings,
            )

        subcommands: dict[str, Command] = {}
        method_options = CommandOptions(parameter_settings=options.parameter_settings)
        for method in cls.methods:
            if method.name in settings.method_skips:
                continue

            method_cli_name = self.commands.translate_command_name(method.name)
            subcommands[method_cli_name] = self.commands.function_command(
                method,
                cli_name_override=method_cli_name,
                pipe_config=pipe_config_for_params(entry.pipe_targets, method.params),
                settings=settings,
                options=method_options,
            )

        for attr_name in dir(entry.obj):
            if attr_name.startswith("_"):
                continue

            attr = getattr(entry.obj, attr_name, None)
            if not isinstance(attr, type):
                continue

            nested_entry = CommandEntry(
                obj=attr,
                name=attr_name,
                description=None,
                aliases=(),
                is_instance=False,
            )
            subcommands[self.commands.translate_command_name(attr_name)] = self.class_tree_command(
                nested_entry,
                current_path,
                settings=settings,
            )

        raw_description = entry.description or (cls.description if cls.has_docstring else None)
        resolved_executable_flags = list(options.executable_flags)
        self.commands.validate_executable_flags(resolved_executable_flags, initializer)
        validate_initializer_positionals(initializer, owner=cli_name, subcommands=subcommands)

        command = Command(
            obj=cls,
            canonical_name=cli_name,
            cli_name=cli_name,
            aliases=entry.aliases,
            raw_description=raw_description,
            help_group=options.help_group,
            parameters=[],
            initializer=initializer,
            subcommands=subcommands or None,
            executable_flags=resolved_executable_flags,
            raw_epilog=None,
            pipe_targets=init_pipe_config,
            command_type="class",
            is_leaf=False,
            parent_path=parent_path,
            metadata={},
            parameter_settings=dict(effective_parameter_settings),
        )
        attach_command_build_settings(
            command,
            settings=settings,
            options=options,
        )

        return command

    def _initializer_taken_flags(self) -> list[str]:
        taken_flags = [*self.context.reserved_flags]
        if self.context.command_key:
            taken_flags.append(self.context.command_key)

        return taken_flags

    def _inspect_class(
        self,
        target: Any,
        *,
        settings: EffectiveCommandSettings,
        init: bool,
    ) -> Class:
        cls = inspect(
            target,
            init=init,
            public=True,
            inherited=settings.include_inherited_methods,
            static_methods=settings.include_staticmethods,
            classmethod=settings.include_classmethods,
            protected=settings.include_protected_methods,
            private=settings.include_private_methods,
        )
        assert isinstance(cls, Class)
        resolve_objinspect_annotations(cls)

        return cls


__all__ = ["ClassCommandBuilder", "class_parameter_settings", "pipe_config_for_params"]

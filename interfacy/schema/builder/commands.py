from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from objinspect import Class, Function, Method

from interfacy.declarations.executable_flags import ExecutableFlag
from interfacy.declarations.options import DEFAULT_COMMAND_OPTIONS, CommandOptions
from interfacy.declarations.params import Param, get_parameter_settings, merge_parameter_settings
from interfacy.declarations.pipes import PipeTargets
from interfacy.models import parse_docstring_args
from interfacy.schema.builder.arguments import ArgumentBuilder
from interfacy.schema.builder.context import EffectiveCommandSettings, SchemaBuildContext
from interfacy.schema.builder.settings import attach_command_build_settings, base_build_settings
from interfacy.schema.model import Argument, Command
from interfacy.schema.validation import (
    argument_option_strings,
    validate_executable_flags_against_tokens,
    validate_positional_order,
)


def callable_parameter_settings(function: Function | Method) -> dict[str, Param]:
    """
    Return the parameter settings declared on a callable.

    Args:
        function (Function | Method): Inspected callable.
    """
    return get_parameter_settings(function.func)


def resolve_cli_name(override: str | None, canonical_name: str | None, fallback: str) -> str:
    """
    Return the first available command name.

    Args:
        override (str | None): Explicit CLI name.
        canonical_name (str | None): Registered canonical name.
        fallback (str): Python object name.
    """
    return override or canonical_name or fallback


@dataclass
class CommandBuilder:
    """Convert functions and methods into leaf schema commands."""

    context: SchemaBuildContext
    arguments: ArgumentBuilder

    def translate_command_name(self, name: str) -> str:
        """
        Return the CLI spelling of a Python command name.

        Args:
            name (str): Python-side name.
        """
        return self.context.flag_strategy.command_translator.translate(name)

    def function_command(
        self,
        function: Function | Method,
        *,
        canonical_name: str | None = None,
        description: str | None = None,
        aliases: tuple[str, ...] = (),
        cli_name_override: str | None = None,
        pipe_config: PipeTargets | None = None,
        settings: EffectiveCommandSettings | None = None,
        options: CommandOptions = DEFAULT_COMMAND_OPTIONS,
    ) -> Command:
        """
        Build a leaf command whose arguments are a callable's parameters.

        Args:
            function (Function | Method): Inspected callable.
            canonical_name (str | None): Canonical command name.
            description (str | None): Description override.
            aliases (tuple[str, ...]): Alternate command names.
            cli_name_override (str | None): CLI name override.
            pipe_config (PipeTargets | None): Pipe configuration; resolved when omitted.
            settings (EffectiveCommandSettings | None): Effective command settings.
            options (CommandOptions): Per-command registration options.
        """
        resolved_settings = settings or base_build_settings(self.context)
        effective_pipe_config = pipe_config
        if pipe_config is None and canonical_name is not None:
            effective_pipe_config = self.context.pipe_target_resolver(
                canonical_name=canonical_name,
                obj_name=function.name,
                aliases=aliases,
                subcommand=None,
                include_default=True,
            )

        pipe_param_names = (
            effective_pipe_config.targeted_parameters() if effective_pipe_config else set()
        )
        effective_parameter_settings = merge_parameter_settings(
            callable_parameter_settings(function),
            options.parameter_settings,
        )
        parameters = self.arguments.from_parameters(
            function.params,
            [*self.context.reserved_flags],
            pipe_param_names,
            settings=resolved_settings,
            parameter_settings=effective_parameter_settings,
        )
        validate_positional_order(parameters, owner=canonical_name or function.name)
        raw_description = description or (function.description if function.has_docstring else None)
        resolved_executable_flags = list(options.executable_flags)
        self.validate_executable_flags(resolved_executable_flags, parameters)

        command = Command(
            obj=function,
            canonical_name=resolve_cli_name(None, canonical_name, function.name),
            cli_name=resolve_cli_name(cli_name_override, canonical_name, function.name),
            aliases=aliases,
            raw_description=raw_description,
            help_group=options.help_group,
            parameters=parameters,
            pipe_targets=pipe_config,
            executable_flags=resolved_executable_flags,
            parameter_settings=dict(effective_parameter_settings),
        )
        attach_command_build_settings(
            command,
            settings=resolved_settings,
            options=options,
        )

        return command

    def method_command(
        self,
        method: Method,
        *,
        canonical_name: str | None = None,
        description: str | None = None,
        aliases: tuple[str, ...] = (),
        settings: EffectiveCommandSettings | None = None,
        options: CommandOptions = DEFAULT_COMMAND_OPTIONS,
    ) -> Command:
        """
        Build a leaf command for a method, with initializer arguments when unbound.

        Args:
            method (Method): Inspected method.
            canonical_name (str | None): Canonical command name.
            description (str | None): Description override.
            aliases (tuple[str, ...]): Alternate command names.
            settings (EffectiveCommandSettings | None): Effective command settings.
            options (CommandOptions): Per-command registration options.
        """
        resolved_settings = settings or base_build_settings(self.context)
        taken_flags = [*self.context.reserved_flags]
        initializer: list[Argument] = []
        is_initialized = hasattr(method.func, "__self__")
        init_pipe_config = self.resolve_pipe_config(
            canonical_name, method.name, aliases, "__init__"
        )
        method_parameter_settings = merge_parameter_settings(
            callable_parameter_settings(method),
            options.parameter_settings,
        )

        if (init := Class(method.cls).init_method) and not is_initialized:
            initializer = self.arguments.from_parameters(
                init.params,
                taken_flags,
                init_pipe_config.targeted_parameters() if init_pipe_config else set(),
                settings=resolved_settings,
                parameter_settings=merge_parameter_settings(
                    get_parameter_settings(method.cls),
                    get_parameter_settings(init.func),
                ),
                descriptions=parse_docstring_args(method.cls.__doc__),
            )

        method_pipe_config = self.resolve_pipe_config(canonical_name, method.name, aliases, None)
        parameters = self.arguments.from_parameters(
            method.params,
            taken_flags,
            method_pipe_config.targeted_parameters() if method_pipe_config else set(),
            settings=resolved_settings,
            parameter_settings=method_parameter_settings,
        )
        validate_positional_order(
            [*initializer, *parameters],
            owner=canonical_name or method.name,
        )

        raw_description = description or (method.description if method.has_docstring else None)
        cli_name = resolve_cli_name(None, canonical_name, method.name)
        resolved_executable_flags = list(options.executable_flags)
        self.validate_executable_flags(resolved_executable_flags, [*initializer, *parameters])

        command = Command(
            obj=method,
            canonical_name=cli_name,
            cli_name=cli_name,
            aliases=aliases,
            raw_description=raw_description,
            help_group=options.help_group,
            parameters=parameters,
            initializer=initializer,
            pipe_targets=method_pipe_config,
            executable_flags=resolved_executable_flags,
            parameter_settings=dict(method_parameter_settings),
        )
        attach_command_build_settings(
            command,
            settings=resolved_settings,
            options=options,
        )

        return command

    def resolve_pipe_config(
        self,
        canonical_name: str | None,
        obj_name: str,
        aliases: tuple[str, ...],
        subcommand: str | None,
    ) -> PipeTargets | None:
        """
        Resolve the non-default pipe configuration registered for a command target.

        Args:
            canonical_name (str | None): Registered command name; None resolves nothing.
            obj_name (str): Python object name.
            aliases (tuple[str, ...]): Alternate command names.
            subcommand (str | None): Subcommand or `__init__` the configuration targets.
        """
        if canonical_name is None:
            return None

        return self.context.pipe_target_resolver(
            canonical_name=canonical_name,
            obj_name=obj_name,
            aliases=aliases,
            subcommand=subcommand,
            include_default=False,
        )

    def validate_executable_flags(
        self,
        executable_flags: list[ExecutableFlag],
        arguments: Sequence[Argument],
    ) -> None:
        """
        Reject executable flags that collide with help flags or argument options.

        Args:
            executable_flags (list[ExecutableFlag]): Executable flags of the command.
            arguments (Sequence[Argument]): Arguments sharing the command's option scope.

        Raises:
            ReservedFlagError: An executable flag token is reserved or taken.
        """
        validate_executable_flags_against_tokens(
            executable_flags,
            argument_option_strings(arguments),
            help_flags=self.context.help_flags,
        )


__all__ = ["CommandBuilder", "callable_parameter_settings", "resolve_cli_name"]

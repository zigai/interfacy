from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from objinspect import Class, Function, Method, Parameter
from objinspect.typing import get_choices, type_args, type_origin

from interfacy.command import Command
from interfacy.exceptions import InvalidCommandError, ReservedFlagError
from interfacy.pipe import PipeTargets
from interfacy.specs.spec import (
    ArgumentKind,
    ArgumentSpec,
    BooleanBehavior,
    CommandSpec,
    ParserSpec,
    ValueShape,
)
from interfacy.util import inverted_bool_flag_name

if TYPE_CHECKING:  # pragma: no cover
    from interfacy.core import InterfacyParser


@dataclass
class ParserSpecBuilder:
    parser: InterfacyParser

    def build(self) -> ParserSpec:
        commands: dict[str, CommandSpec] = {}
        for canonical_name, cmd in self.parser.commands.items():
            commands[canonical_name] = self._command_spec_from_command(cmd)

        commands_help = None
        if len(commands) > 1:
            commands_help = self.parser.theme.get_help_for_multiple_commands(self.parser.commands)

        return ParserSpec(
            raw_description=self.parser.description,
            raw_epilog=self.parser.epilog,
            commands=commands,
            command_key=getattr(self.parser, "COMMAND_KEY", None),
            allow_args_from_file=self.parser.allow_args_from_file,
            pipe_targets=self.parser.pipe_targets_default,
            theme=self.parser.theme,
            commands_help=commands_help,
        )

    def _command_spec_from_command(self, command: Command) -> CommandSpec:
        obj = command.obj
        if isinstance(obj, Function):
            return self._function_spec(obj, command)
        if isinstance(obj, Method):
            return self._method_spec(obj, command)
        if isinstance(obj, Class):
            return self._class_spec(obj, command)
        raise InvalidCommandError(obj)

    def _function_spec(
        self,
        function: Function | Method,
        command: Command | None = None,
        *,
        cli_name_override: str | None = None,
        pipe_config: PipeTargets | None = None,
    ) -> CommandSpec:
        taken_flags = [*self.parser.RESERVED_FLAGS]
        if pipe_config is None and command is not None:
            pipe_config = command.get_pipe_targets()

        pipe_param_names = pipe_config.targeted_parameters() if pipe_config else set()

        parameters = [
            self._argument_from_parameter(param, taken_flags, pipe_param_names)
            for param in function.params
        ]
        raw_description = (
            command.description
            if command and command.description
            else (function.description if function.has_docstring else None)
        )
        cli_name = self._resolve_cli_name(cli_name_override, command, function.name)

        return CommandSpec(
            obj=function,
            canonical_name=self._resolve_cli_name(None, command, function.name),
            cli_name=cli_name,
            aliases=command.aliases if command else (),
            raw_description=raw_description,
            parameters=parameters,
            pipe_targets=pipe_config,
            theme=self.parser.theme,
        )

    def _method_spec(self, method: Method, command: Command | None = None) -> CommandSpec:
        taken_flags = [*self.parser.RESERVED_FLAGS]

        initializer: list[ArgumentSpec] = []
        is_initialized = hasattr(method.func, "__self__")
        init_pipe_config: PipeTargets | None = None
        if command is not None:
            init_pipe_config = command.get_pipe_targets(subcommand="__init__")
        init_pipe_names = init_pipe_config.targeted_parameters() if init_pipe_config else set()

        if (init := Class(method.cls).init_method) and not is_initialized:
            initializer = [
                self._argument_from_parameter(param, taken_flags, init_pipe_names)
                for param in init.params
            ]

        method_pipe_config = command.get_pipe_targets() if command is not None else None
        pipe_param_names = method_pipe_config.targeted_parameters() if method_pipe_config else set()

        parameters = [
            self._argument_from_parameter(param, taken_flags, pipe_param_names)
            for param in method.params
        ]

        raw_description = (
            command.description
            if command and command.description
            else (method.description if method.has_docstring else None)
        )
        cli_name = self._resolve_cli_name(None, command, method.name)

        return CommandSpec(
            obj=method,
            canonical_name=cli_name,
            cli_name=cli_name,
            aliases=command.aliases if command else (),
            raw_description=raw_description,
            parameters=parameters,
            initializer=initializer,
            pipe_targets=method_pipe_config,
            theme=self.parser.theme,
        )

    def _class_spec(self, cls: Class, command: Command | None = None) -> CommandSpec:
        taken_flags = [*self.parser.RESERVED_FLAGS]
        command_key = getattr(self.parser, "COMMAND_KEY", None)
        if command_key:
            taken_flags.append(command_key)

        initializer: list[ArgumentSpec] = []
        class_pipe_config = command.get_pipe_targets() if command is not None else None
        init_pipe_config = None
        if command is not None:
            init_pipe_config = command.get_pipe_targets(subcommand="__init__")
            if init_pipe_config is None:
                init_pipe_config = class_pipe_config

        if cls.has_init and not cls.is_initialized:
            init_pipe_names = init_pipe_config.targeted_parameters() if init_pipe_config else set()
            initializer = [
                self._argument_from_parameter(param, taken_flags, init_pipe_names)
                for param in cls.get_method("__init__").params
            ]

        subcommands: dict[str, CommandSpec] = {}
        for method in cls.methods:
            if method.name in self.parser.method_skips:
                continue

            method_cli_name = self.parser.flag_strategy.command_translator.translate(method.name)
            sub_pipe_config = None
            if command is not None:
                sub_pipe_config = (
                    command.get_pipe_targets(subcommand=method_cli_name)
                    or command.get_pipe_targets(subcommand=method.name)
                    or class_pipe_config
                )
            subcommands[method_cli_name] = self._function_spec(
                method,
                command=None,
                cli_name_override=method_cli_name,
                pipe_config=sub_pipe_config,
            )

        raw_description = (
            command.description
            if command and command.description
            else (cls.description if cls.has_docstring else None)
        )
        cli_name = self._resolve_cli_name(None, command, cls.name)

        return CommandSpec(
            obj=cls,
            canonical_name=cli_name,
            cli_name=cli_name,
            aliases=command.aliases if command else (),
            raw_description=raw_description,
            parameters=[],
            initializer=initializer,
            subcommands=subcommands,
            raw_epilog=self.parser.theme.get_help_for_class(cls),
            pipe_targets=class_pipe_config,
            theme=self.parser.theme,
        )

    def _argument_from_parameter(
        self,
        param: Parameter,
        taken_flags: list[str],
        pipe_param_names: set[str] | None = None,
    ) -> ArgumentSpec:
        translated_name = self.parser.flag_strategy.argument_translator.translate(param.name)
        if translated_name in taken_flags:
            raise ReservedFlagError(translated_name)

        flags = self.parser.flag_strategy.get_arg_flags(
            translated_name,
            param,
            taken_flags,
            self.parser.abbreviation_gen,
        )
        taken_flags.append(translated_name)
        help_text = self.parser.theme.get_help_for_parameter(param)

        parser_func: Callable[[str], Any] | None = None
        value_shape = ValueShape.SINGLE
        nargs: str | None = None
        default_value: Any = param.default if getattr(param, "has_default", False) else None
        parsed_type: type[Any] | None = param.type if param.is_typed else None
        choices = get_choices(param.type) if param.is_typed else None
        boolean_behavior: BooleanBehavior | None = None

        if param.is_typed:
            t_origin = type_origin(param.type)
            is_list_alias = t_origin is list

            if is_list_alias or param.type is list:
                value_shape = ValueShape.LIST
                nargs = "*"
                if is_list_alias:
                    t_args = type_args(param.type)

                    if t_args:
                        parsed_type = t_args[0]
                        parser_func = self.parser.type_parser.get_parse_func(t_args[0])

                elif param.type is list:
                    parser_func = None

            elif param.type is bool:
                value_shape = ValueShape.FLAG
                supports_negative = any(flag.startswith("--") for flag in flags)
                negative_form = None

                if supports_negative:
                    long_flags = [flag for flag in flags if flag.startswith("--")]
                    long_name = long_flags[0][2:] if long_flags else translated_name
                    negative_form = f"--{inverted_bool_flag_name(long_name)}"

                default_value = param.default if getattr(param, "has_default", False) else False

                boolean_behavior = BooleanBehavior(
                    supports_negative=supports_negative,
                    negative_form=negative_form,
                    default=default_value,
                )
            else:
                parser_func = self.parser.type_parser.get_parse_func(param.type)

        if not param.is_required and param.is_typed and param.type is not bool:
            default_value = param.default

        metavar = None
        if self.parser.theme.clear_metavar and not param.is_required:
            metavar = "\b"

        kind = ArgumentKind.POSITIONAL
        if any(flag.startswith("-") for flag in flags):
            kind = ArgumentKind.OPTION

        accepts_stdin = pipe_param_names is not None and param.name in pipe_param_names
        pipe_required = accepts_stdin and param.is_required

        if accepts_stdin:
            if (
                value_shape is ValueShape.SINGLE
                and kind is ArgumentKind.POSITIONAL
                and nargs is None
            ):
                nargs = "?"
            required = False
        else:
            required = param.is_required

        return ArgumentSpec(
            name=param.name,
            display_name=translated_name,
            kind=kind,
            value_shape=value_shape,
            flags=flags,
            required=required,
            default=default_value,
            help=help_text,
            type=parsed_type,
            parser=parser_func,
            metavar=metavar,
            nargs=nargs,
            boolean_behavior=boolean_behavior,
            choices=choices,
            accepts_stdin=accepts_stdin,
            pipe_required=pipe_required,
        )

    def _resolve_cli_name(
        self,
        override: str | None,
        command: Command | None,
        fallback: str,
    ) -> str:
        if override:
            return override
        if command and command.name:
            return command.name
        return fallback

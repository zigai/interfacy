from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from objinspect import Class, Function, Method, Parameter
from objinspect.typing import get_choices, type_args

from interfacy.exceptions import InvalidCommandError, ReservedFlagError
from interfacy.pipe import PipeTargets
from interfacy.schema.schema import (
    Argument,
    ArgumentKind,
    BooleanBehavior,
    Command,
    ParserSchema,
    ValueShape,
)
from interfacy.util import (
    extract_optional_union_list,
    inverted_bool_flag_name,
    is_list_or_list_alias,
)

if TYPE_CHECKING:  # pragma: no cover
    from interfacy.core import InterfacyParser


@dataclass
class ParserSchemaBuilder:
    parser: InterfacyParser

    def build(self) -> ParserSchema:
        commands: dict[str, Command] = {}
        for canonical_name, command in self.parser.commands.items():
            rebuilt = self.build_command_spec_for(
                command.obj,
                canonical_name=command.canonical_name,
                description=command.raw_description,
                aliases=command.aliases,
            )
            commands[canonical_name] = rebuilt

        commands_help = None
        if len(commands) > 1:
            commands_help = self.parser.help_layout.get_help_for_multiple_commands(
                self.parser.commands
            )

        return ParserSchema(
            raw_description=self.parser.description,
            raw_epilog=self.parser.epilog,
            commands=commands,
            command_key=self.parser.COMMAND_KEY,
            allow_args_from_file=self.parser.allow_args_from_file,
            pipe_targets=self.parser.pipe_targets_default,
            theme=self.parser.help_layout,
            commands_help=commands_help,
        )

    def build_command_spec_for(
        self,
        obj: Class | Function | Method,
        *,
        canonical_name: str,
        description: str | None = None,
        aliases: tuple[str, ...] = (),
    ) -> Command:
        if isinstance(obj, Function):
            return self._function_spec(
                obj,
                canonical_name=canonical_name,
                description=description,
                aliases=aliases,
            )

        if isinstance(obj, Method):
            return self._method_command(
                obj,
                canonical_name=canonical_name,
                description=description,
                aliases=aliases,
            )

        if isinstance(obj, Class):
            return self._class_command(
                obj,
                canonical_name=canonical_name,
                description=description,
                aliases=aliases,
            )
        raise InvalidCommandError(obj)

    def _function_spec(
        self,
        function: Function | Method,
        *,
        canonical_name: str | None = None,
        description: str | None = None,
        aliases: tuple[str, ...] = (),
        cli_name_override: str | None = None,
        pipe_config: PipeTargets | None = None,
    ) -> Command:
        taken_flags = [*self.parser.RESERVED_FLAGS]
        if pipe_config is None and canonical_name is not None:
            pipe_config = self.parser.resolve_pipe_targets_by_names(
                canonical_name=canonical_name,
                obj_name=function.name,
                aliases=aliases,
                subcommand=None,
                include_default=False,
            )

        pipe_param_names = pipe_config.targeted_parameters() if pipe_config else set()

        parameters = [
            self._argument_from_parameter(param, taken_flags, pipe_param_names)
            for param in function.params
        ]
        raw_description = (
            description
            if description
            else (function.description if function.has_docstring else None)
        )
        cli_name = self._resolve_cli_name(
            override=cli_name_override,
            canonical_name=canonical_name,
            fallback=function.name,
        )

        return Command(
            obj=function,
            canonical_name=self._resolve_cli_name(None, canonical_name, function.name),
            cli_name=cli_name,
            aliases=aliases,
            raw_description=raw_description,
            parameters=parameters,
            pipe_targets=pipe_config,
            help_layout=self.parser.help_layout,
        )

    def _method_command(
        self,
        method: Method,
        *,
        canonical_name: str | None = None,
        description: str | None = None,
        aliases: tuple[str, ...] = (),
    ) -> Command:
        taken_flags = [*self.parser.RESERVED_FLAGS]

        initializer: list[Argument] = []
        is_initialized = hasattr(method.func, "__self__")
        init_pipe_config: PipeTargets | None = None
        if canonical_name is not None:
            init_pipe_config = self.parser.resolve_pipe_targets_by_names(
                canonical_name=canonical_name,
                obj_name=method.name,
                aliases=aliases,
                subcommand="__init__",
                include_default=False,
            )
        init_pipe_names = init_pipe_config.targeted_parameters() if init_pipe_config else set()

        if (init := Class(method.cls).init_method) and not is_initialized:
            initializer = [
                self._argument_from_parameter(param, taken_flags, init_pipe_names)
                for param in init.params
            ]

        method_pipe_config = None
        if canonical_name is not None:
            method_pipe_config = self.parser.resolve_pipe_targets_by_names(
                canonical_name=canonical_name,
                obj_name=method.name,
                aliases=aliases,
                subcommand=None,
                include_default=False,
            )
        pipe_param_names = method_pipe_config.targeted_parameters() if method_pipe_config else set()

        parameters = [
            self._argument_from_parameter(param, taken_flags, pipe_param_names)
            for param in method.params
        ]

        raw_description = (
            description if description else (method.description if method.has_docstring else None)
        )
        cli_name = self._resolve_cli_name(None, canonical_name, method.name)

        return Command(
            obj=method,
            canonical_name=cli_name,
            cli_name=cli_name,
            aliases=aliases,
            raw_description=raw_description,
            parameters=parameters,
            initializer=initializer,
            pipe_targets=method_pipe_config,
            help_layout=self.parser.help_layout,
        )

    def _class_command(
        self,
        cls: Class,
        *,
        canonical_name: str | None = None,
        description: str | None = None,
        aliases: tuple[str, ...] = (),
    ) -> Command:
        taken_flags = [*self.parser.RESERVED_FLAGS]
        command_key = self.parser.COMMAND_KEY
        if command_key:
            taken_flags.append(command_key)

        initializer: list[Argument] = []
        class_pipe_config = None
        init_pipe_config = None
        if canonical_name is not None:
            class_pipe_config = self.parser.resolve_pipe_targets_by_names(
                canonical_name=canonical_name,
                obj_name=cls.name,
                aliases=aliases,
                subcommand=None,
                include_default=False,
            )
            init_pipe_config = (
                self.parser.resolve_pipe_targets_by_names(
                    canonical_name=canonical_name,
                    obj_name=cls.name,
                    aliases=aliases,
                    subcommand="__init__",
                    include_default=False,
                )
                or class_pipe_config
            )

        if cls.has_init and not cls.is_initialized:
            init_pipe_names = init_pipe_config.targeted_parameters() if init_pipe_config else set()
            initializer = [
                self._argument_from_parameter(param, taken_flags, init_pipe_names)
                for param in cls.get_method("__init__").params
            ]

        subcommands: dict[str, Command] = {}
        for method in cls.methods:
            if method.name in self.parser.method_skips:
                continue

            method_cli_name = self.parser.flag_strategy.command_translator.translate(method.name)
            sub_pipe_config = None
            if canonical_name is not None:
                sub_pipe_config = (
                    self.parser.resolve_pipe_targets_by_names(
                        canonical_name=canonical_name,
                        obj_name=cls.name,
                        aliases=aliases,
                        subcommand=method_cli_name,
                        include_default=False,
                    )
                    or self.parser.resolve_pipe_targets_by_names(
                        canonical_name=canonical_name,
                        obj_name=cls.name,
                        aliases=aliases,
                        subcommand=method.name,
                        include_default=False,
                    )
                    or class_pipe_config
                )

            subcommands[method_cli_name] = self._function_spec(
                method,
                canonical_name=None,
                description=None,
                aliases=(),
                cli_name_override=method_cli_name,
                pipe_config=sub_pipe_config,
            )

        raw_description = (
            description if description else (cls.description if cls.has_docstring else None)
        )
        cli_name = self._resolve_cli_name(None, canonical_name, cls.name)

        return Command(
            obj=cls,
            canonical_name=cli_name,
            cli_name=cli_name,
            aliases=aliases,
            raw_description=raw_description,
            parameters=[],
            initializer=initializer,
            subcommands=subcommands,
            raw_epilog=self.parser.help_layout.get_help_for_class(cls),
            pipe_targets=class_pipe_config,
            help_layout=self.parser.help_layout,
        )

    def _argument_from_parameter(
        self,
        param: Parameter,
        taken_flags: list[str],
        pipe_param_names: set[str] | None = None,
    ) -> Argument:
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
        help_text = self.parser.help_layout.get_help_for_parameter(param, tuple(flags))

        parser_func: Callable[[str], Any] | None = None
        value_shape = ValueShape.SINGLE
        nargs: str | None = None
        default_value: Any = param.default if param.has_default else None
        parsed_type: type[Any] | None = param.type if param.is_typed else None
        choices = get_choices(param.type) if param.is_typed else None
        boolean_behavior: BooleanBehavior | None = None
        is_optional_union_list = False

        if param.is_typed:
            optional_union_list = extract_optional_union_list(param.type)
            list_annotation: Any | None = None
            element_type: Any | None = None

            if optional_union_list:
                list_annotation, element_type = optional_union_list
                is_optional_union_list = True
            elif is_list_or_list_alias(param.type):
                list_annotation = param.type
                element_args = type_args(param.type)
                element_type = element_args[0] if element_args else None

            if list_annotation is not None:
                value_shape = ValueShape.LIST
                nargs = "*"
                if element_type is not None:
                    parsed_type = element_type
                    parser_func = self.parser.type_parser.get_parse_func(element_type)
                else:
                    parsed_type = None
                    parser_func = None

                if is_optional_union_list and not param.has_default:
                    default_value = []

            elif param.type is bool:
                value_shape = ValueShape.FLAG
                supports_negative = any(flag.startswith("--") for flag in flags)
                negative_form = None

                if supports_negative:
                    long_flags = [flag for flag in flags if flag.startswith("--")]
                    long_name = long_flags[0][2:] if long_flags else translated_name
                    negative_form = f"--{inverted_bool_flag_name(long_name)}"

                default_value = param.default if param.has_default else False

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
        if self.parser.help_layout.clear_metavar and not param.is_required:
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
            required = False if is_optional_union_list else param.is_required

        return Argument(
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
        canonical_name: str | None,
        fallback: str,
    ) -> str:
        if override:
            return override
        if canonical_name:
            return canonical_name
        return fallback

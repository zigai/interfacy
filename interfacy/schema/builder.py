from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from inspect import Parameter as StdParameter
from typing import TYPE_CHECKING, Any

from objinspect import Class, Function, Method, Parameter, inspect
from objinspect.typing import type_args
from stdl.st import ansi_len, with_style

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
    get_fixed_tuple_info,
    get_param_choices,
    inverted_bool_flag_name,
    is_fixed_tuple,
    is_list_or_list_alias,
    simplified_type_name,
)

if TYPE_CHECKING:  # pragma: no cover
    from interfacy.core import InterfacyParser
    from interfacy.group import CommandEntry, CommandGroup


@dataclass
class ParserSchemaBuilder:
    parser: InterfacyParser

    def build(self) -> ParserSchema:
        commands: dict[str, Command] = {}
        for canonical_name, command in self.parser.commands.items():
            if command.command_type in ("group", "instance") or (
                not command.is_leaf and command.obj is None
            ):
                commands[canonical_name] = command
            else:
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
            metadata=dict(getattr(self.parser, "metadata", {})),
        )

    def _prepare_layout_for_params(self, params: list[Parameter]) -> None:
        if not params:
            return
        layout = self.parser.help_layout
        if layout is None:
            return
        try:
            layout.prepare_default_field_width_for_params(params)
        except Exception:
            return

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

        self._prepare_layout_for_params(function.params)
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

        init_params: list[Parameter] = []
        if (init := Class(method.cls).init_method) and not is_initialized:
            init_params = init.params
            self._prepare_layout_for_params([*init_params, *method.params])
            initializer = [
                self._argument_from_parameter(param, taken_flags, init_pipe_names)
                for param in init.params
            ]
        else:
            self._prepare_layout_for_params(method.params)

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
            self._prepare_layout_for_params(cls.get_method("__init__").params)
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
        annotation = param.type
        if isinstance(annotation, str):
            simple_name = simplified_type_name(annotation)
            base_name = simple_name[:-1] if simple_name.endswith("?") else simple_name
            builtin_map = {"bool": bool, "int": int, "float": float, "str": str}
            if base_name in builtin_map:
                annotation = builtin_map[base_name]

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
        nargs: str | int | None = None
        default_value: Any = param.default if param.has_default else None
        parsed_type: type[Any] | None = annotation if param.is_typed else None
        choices = get_param_choices(param, for_display=False) if param.is_typed else None
        if choices is not None:
            choices = tuple(choices)
        boolean_behavior: BooleanBehavior | None = None
        is_optional_union_list = False
        tuple_element_parsers: tuple[Callable[[str], Any], ...] | None = None

        if param.kind == StdParameter.VAR_POSITIONAL:
            value_shape = ValueShape.LIST
            nargs = "*"
            default_value = ()  # Empty tuple as default for *args
            if param.is_typed:
                parsed_type = annotation
                if annotation is not str:
                    parser_func = self.parser.type_parser.get_parse_func(annotation)
        elif param.is_typed:
            optional_union_list = extract_optional_union_list(annotation)
            list_annotation: Any | None = None
            element_type: Any | None = None

            if optional_union_list:
                list_annotation, element_type = optional_union_list
                is_optional_union_list = True
            elif is_list_or_list_alias(annotation):
                list_annotation = annotation
                element_args = type_args(annotation)
                element_type = element_args[0] if element_args else None

            if list_annotation is not None:
                value_shape = ValueShape.LIST
                nargs = "*"
                if element_type is not None:
                    parsed_type = element_type
                    if element_type is not str:
                        parser_func = self.parser.type_parser.get_parse_func(element_type)
                else:
                    parsed_type = None
                    parser_func = None

                if is_optional_union_list and not param.has_default:
                    default_value = []

            elif is_fixed_tuple(annotation):
                tuple_info = get_fixed_tuple_info(annotation)
                if tuple_info:
                    element_count, element_types = tuple_info
                    value_shape = ValueShape.TUPLE
                    nargs = element_count

                    first_type = element_types[0]
                    all_same_type = all(t == first_type for t in element_types)

                    if all_same_type:
                        parsed_type = first_type
                        element_parser = self.parser.type_parser.get_parse_func(first_type)

                        def make_tuple_parser(
                            elem_parser: Callable[[str], Any],
                        ) -> Callable[[str], Any]:
                            return elem_parser

                        parser_func = make_tuple_parser(element_parser)
                    else:
                        tuple_element_parsers = tuple(
                            self.parser.type_parser.get_parse_func(t) for t in element_types
                        )
                        parsed_type = str
                        parser_func = None

            elif annotation is bool:
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
                if annotation is not str:
                    parser_func = self.parser.type_parser.get_parse_func(annotation)

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
            tuple_element_parsers=tuple_element_parsers,
        )

    def build_from_group(
        self,
        group: CommandGroup,
        parent_path: tuple[str, ...] = (),
        canonical_name: str | None = None,
    ) -> Command:
        """Build Command schema from a CommandGroup (manual construction)."""
        cli_name = canonical_name or self.parser.flag_strategy.command_translator.translate(
            group.name
        )
        current_path = (*parent_path, cli_name)

        initializer: list[Argument] = []
        if group._group_args_source is not None:
            initializer = self._build_args_from_source(group._group_args_source)

        subcommands: dict[str, Command] = {}

        for name, subgroup in group._subgroups.items():
            sub_cli_name = self.parser.flag_strategy.command_translator.translate(name)
            subcommands[sub_cli_name] = self.build_from_group(subgroup, current_path)

        for name, entry in group._commands.items():
            sub_cli_name = self.parser.flag_strategy.command_translator.translate(name)
            subcommands[sub_cli_name] = self._build_command_entry(entry, current_path)

        raw_epilog = None
        if subcommands:
            raw_epilog = self._build_group_epilog(subcommands)

        return Command(
            obj=None,
            canonical_name=cli_name,
            cli_name=cli_name,
            aliases=group.aliases,
            raw_description=group.description,
            parameters=[],
            initializer=initializer,
            subcommands=subcommands if subcommands else None,
            raw_epilog=raw_epilog,
            help_layout=self.parser.help_layout,
            command_type="group",
            is_leaf=False,
            parent_path=parent_path,
        )

    def _build_args_from_source(self, source: type | Callable) -> list[Argument]:
        """Build argument list from a class __init__ or callable signature."""
        obj = inspect(source, init=True)
        taken_flags = [*self.parser.RESERVED_FLAGS]

        if isinstance(obj, Class) and obj.init_method:
            self._prepare_layout_for_params(obj.init_method.params)
            return [
                self._argument_from_parameter(param, taken_flags, set())
                for param in obj.init_method.params
            ]
        elif isinstance(obj, Function):
            self._prepare_layout_for_params(obj.params)
            return [
                self._argument_from_parameter(param, taken_flags, set()) for param in obj.params
            ]
        return []

    def _build_command_entry(
        self,
        entry: CommandEntry,
        parent_path: tuple[str, ...],
    ) -> Command:
        """Build Command from a CommandEntry (function/class/instance)."""
        if entry.is_instance:
            return self._build_from_instance(entry, parent_path)
        elif isinstance(entry.obj, type):
            return self._build_from_class_recursive(entry, parent_path)
        else:
            obj = inspect(entry.obj)
            if isinstance(obj, (Function, Method)):
                return self._function_spec(
                    obj,
                    canonical_name=entry.name,
                    description=entry.description,
                    aliases=entry.aliases,
                )
            raise InvalidCommandError(entry.obj)

    def _build_from_instance(
        self,
        entry: CommandEntry,
        parent_path: tuple[str, ...],
    ) -> Command:
        """Build from a class instance - methods as commands, no __init__ args."""
        instance = entry.obj
        cls = inspect(
            type(instance),
            init=False,
            public=True,
            inherited=self.parser.include_inherited_methods,
            static_methods=True,
            classmethod=self.parser.include_classmethods,
        )

        subcommands: dict[str, Command] = {}
        for method in cls.methods:
            if method.name.startswith("_") or method.name in self.parser.method_skips:
                continue
            method_cli_name = self.parser.flag_strategy.command_translator.translate(method.name)
            subcommands[method_cli_name] = self._function_spec(
                method,
                canonical_name=None,
                description=None,
                aliases=(),
                cli_name_override=method_cli_name,
            )

        cli_name = self.parser.flag_strategy.command_translator.translate(entry.name)
        raw_description = entry.description or (cls.description if cls.has_docstring else None)

        raw_epilog = None
        if subcommands:
            raw_epilog = self._build_group_epilog(subcommands)

        return Command(
            obj=cls,
            canonical_name=cli_name,
            cli_name=cli_name,
            aliases=entry.aliases,
            raw_description=raw_description,
            parameters=[],
            initializer=[],
            subcommands=subcommands if subcommands else None,
            raw_epilog=raw_epilog,
            help_layout=self.parser.help_layout,
            command_type="instance",
            is_leaf=False,
            is_instance=True,
            parent_path=parent_path,
            stored_instance=instance,
        )

    def _build_from_class_recursive(
        self,
        entry: CommandEntry,
        parent_path: tuple[str, ...],
    ) -> Command:
        """Build from a class - methods AND nested classes (recursive)."""
        from interfacy.group import CommandEntry as CE

        cls = inspect(
            entry.obj,
            init=True,
            public=True,
            inherited=self.parser.include_inherited_methods,
            static_methods=True,
            classmethod=self.parser.include_classmethods,
        )

        cli_name = self.parser.flag_strategy.command_translator.translate(entry.name)
        current_path = (*parent_path, cli_name)

        taken_flags = [*self.parser.RESERVED_FLAGS]
        command_key = self.parser.COMMAND_KEY
        if command_key:
            taken_flags.append(command_key)

        initializer: list[Argument] = []
        if cls.has_init and not cls.is_initialized:
            self._prepare_layout_for_params(cls.get_method("__init__").params)
            initializer = [
                self._argument_from_parameter(param, taken_flags, set())
                for param in cls.get_method("__init__").params
            ]

        subcommands: dict[str, Command] = {}

        for method in cls.methods:
            if method.name.startswith("_") or method.name in self.parser.method_skips:
                continue
            method_cli_name = self.parser.flag_strategy.command_translator.translate(method.name)
            subcommands[method_cli_name] = self._function_spec(
                method,
                canonical_name=None,
                description=None,
                aliases=(),
                cli_name_override=method_cli_name,
            )

        for attr_name in dir(entry.obj):
            if attr_name.startswith("_"):
                continue
            attr = getattr(entry.obj, attr_name, None)
            if attr is None:
                continue
            if isinstance(attr, type):
                nested_entry = CE(
                    obj=attr,
                    name=attr_name,
                    description=None,
                    aliases=(),
                    is_instance=False,
                )
                nested_cli_name = self.parser.flag_strategy.command_translator.translate(attr_name)
                subcommands[nested_cli_name] = self._build_from_class_recursive(
                    nested_entry, current_path
                )

        raw_description = entry.description or (cls.description if cls.has_docstring else None)

        raw_epilog = None
        if subcommands:
            raw_epilog = self._build_group_epilog(subcommands)

        return Command(
            obj=cls,
            canonical_name=cli_name,
            cli_name=cli_name,
            aliases=entry.aliases,
            raw_description=raw_description,
            parameters=[],
            initializer=initializer,
            subcommands=subcommands if subcommands else None,
            raw_epilog=raw_epilog,
            help_layout=self.parser.help_layout,
            command_type="class",
            is_leaf=False,
            parent_path=parent_path,
        )

    def _build_group_epilog(self, subcommands: dict[str, Command]) -> str:
        """Build epilog text listing available subcommands."""
        layout = self.parser.help_layout
        title = getattr(layout, "commands_title", "commands:")
        if hasattr(layout, "_format_commands_title"):
            try:
                title = layout._format_commands_title()
            except Exception:
                title = getattr(layout, "commands_title", "commands:")
        lines = [title]
        max_name_len = max(len(cmd.cli_name) for cmd in subcommands.values()) if subcommands else 0
        ljust = self.parser.help_layout.get_commands_ljust(max_name_len)
        name_style = getattr(layout, "command_name_style", None)

        for cmd in subcommands.values():
            raw_name = cmd.cli_name
            styled_name = with_style(raw_name, name_style) if name_style else raw_name
            pad = max(0, ljust - (3 + ansi_len(styled_name)))
            name_col = f"   {styled_name}{' ' * pad}"
            desc = cmd.raw_description or ""
            if desc:
                first_line = desc.split("\n")[0].strip()
                lines.append(f"{name_col} {first_line}")
            else:
                lines.append(name_col)

        return "\n".join(lines)

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

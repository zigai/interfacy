from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import MISSING, dataclass, fields, is_dataclass
from inspect import Parameter as InspectParameter
from types import NoneType
from typing import TYPE_CHECKING, Any

from objinspect import Class, Function, Method, Parameter, inspect
from objinspect.typing import is_union_type, type_args
from stdl.st import ansi_len, with_style

from interfacy.exceptions import InvalidCommandError, ReservedFlagError
from interfacy.pipe import PipeTargets
from interfacy.schema.schema import (
    MODEL_DEFAULT_UNSET,
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
    resolve_type_alias,
    simplified_type_name,
)

if TYPE_CHECKING:  # pragma: no cover
    from interfacy.core import InterfacyParser
    from interfacy.group import CommandEntry, CommandGroup


@dataclass
class _ParamSpec:
    name: str
    type: Any
    is_typed: bool
    has_default: bool
    default: Any
    is_required: bool
    is_optional: bool
    kind: InspectParameter
    description: str | None = None


@dataclass
class _ModelFieldSpec:
    name: str
    annotation: Any
    required: bool
    default: Any
    description: str | None = None


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
            arg
            for param in function.params
            for arg in self._argument_from_parameter(param, taken_flags, pipe_param_names)
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
                arg
                for param in init.params
                for arg in self._argument_from_parameter(param, taken_flags, init_pipe_names)
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
            arg
            for param in method.params
            for arg in self._argument_from_parameter(param, taken_flags, pipe_param_names)
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
                arg
                for param in cls.get_method("__init__").params
                for arg in self._argument_from_parameter(param, taken_flags, init_pipe_names)
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
    ) -> list[Argument]:
        annotation = resolve_type_alias(param.type)
        if isinstance(annotation, str):
            simple_name = simplified_type_name(annotation)
            base_name = simple_name[:-1] if simple_name.endswith("?") else simple_name
            builtin_map = {"bool": bool, "int": int, "float": float, "str": str}
            if base_name in builtin_map:
                annotation = builtin_map[base_name]

        if param.is_typed:
            model_type, is_optional_model = self._unwrap_optional(annotation)
            if self._should_expand_model(model_type):
                return self._expand_model_parameter(
                    param=param,
                    model_type=model_type,
                    is_optional_model=is_optional_model,
                    taken_flags=taken_flags,
                )

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

        spec = _ParamSpec(
            name=param.name,
            type=annotation,
            is_typed=param.is_typed,
            has_default=param.has_default,
            default=param.default if param.has_default else None,
            is_required=param.is_required,
            is_optional=getattr(param, "is_optional", False),
            kind=param.kind,
            description=param.description,
        )

        return [
            self._argument_from_spec(
                spec=spec,
                translated_name=translated_name,
                flags=flags,
                taken_flags=taken_flags,
                pipe_param_names=pipe_param_names,
                allow_optional_union_list=True,
                suppress_default=False,
            )
        ]

    def _nested_separator(self) -> str:
        return getattr(self.parser.flag_strategy, "nested_separator", ".")

    def _unwrap_optional(self, annotation: Any) -> tuple[Any, bool]:
        if not is_union_type(annotation):
            return annotation, False
        union_args = type_args(annotation)
        if NoneType not in union_args or len(union_args) != 2:
            return annotation, False
        inner = next(arg for arg in union_args if arg is not NoneType)
        return inner, True

    def _is_pydantic_model(self, typ: Any) -> bool:
        return isinstance(typ, type) and (
            hasattr(typ, "model_fields") or hasattr(typ, "__fields__")
        )

    def _is_plain_class_model(self, typ: Any) -> bool:
        if not isinstance(typ, type):
            return False
        if typ in {str, int, float, bool, bytes, list, dict, tuple, set}:
            return False
        try:
            cls_info = Class(
                typ,
                init=True,
                public=True,
                inherited=True,
                static_methods=True,
                protected=False,
                private=False,
                classmethod=True,
            )
        except Exception:
            return False
        init_method = cls_info.init_method
        if init_method is None:
            return False
        params = [
            p
            for p in init_method.params
            if p.kind not in (InspectParameter.VAR_POSITIONAL, InspectParameter.VAR_KEYWORD)
        ]
        return len(params) > 0

    def _should_expand_model(self, param_type: Any) -> bool:
        if not getattr(self.parser, "expand_model_params", True):
            return False
        if not isinstance(param_type, type):
            return False
        if is_dataclass(param_type) or self._is_pydantic_model(param_type):
            return True
        return self._is_plain_class_model(param_type)

    def _get_model_fields(self, model_type: type) -> list[_ModelFieldSpec]:
        if is_dataclass(model_type):
            arg_docs = self._parse_docstring_args(model_type.__doc__)
            result: list[_ModelFieldSpec] = []
            for f in fields(model_type):
                required = f.default is MISSING and f.default_factory is MISSING
                default = None
                if f.default is not MISSING:
                    default = f.default
                elif f.default_factory is not MISSING:  # type: ignore[comparison-overlap]
                    default = f.default_factory  # type: ignore[assignment]
                description = None
                if isinstance(f.metadata, dict):
                    description = f.metadata.get("description") or f.metadata.get("help")
                if description is None:
                    description = arg_docs.get(f.name)
                result.append(
                    _ModelFieldSpec(
                        name=f.name,
                        annotation=f.type,
                        required=required,
                        default=default,
                        description=description,
                    )
                )
            return result

        if hasattr(model_type, "model_fields"):
            result = []
            field_map = getattr(model_type, "model_fields", {}) or {}
            for name, info in field_map.items():
                annotation = getattr(info, "annotation", None)
                if annotation is None and hasattr(model_type, "__annotations__"):
                    annotation = model_type.__annotations__.get(name)
                required = False
                if hasattr(info, "is_required"):
                    try:
                        required = bool(info.is_required())  # type: ignore[operator]
                    except TypeError:
                        required = bool(info.is_required)  # type: ignore[truthy-bool]
                default = getattr(info, "default", None)
                if required:
                    default = None
                description = getattr(info, "description", None)
                result.append(
                    _ModelFieldSpec(
                        name=name,
                        annotation=annotation,
                        required=required,
                        default=default,
                        description=description,
                    )
                )
            return result

        if hasattr(model_type, "__fields__"):
            result = []
            field_map = getattr(model_type, "__fields__", {}) or {}
            for name, info in field_map.items():
                annotation = getattr(info, "outer_type_", None) or getattr(info, "type_", None)
                required = bool(getattr(info, "required", False))
                default = getattr(info, "default", None)
                if required:
                    default = None
                description = None
                if hasattr(info, "field_info"):
                    description = getattr(info.field_info, "description", None)
                result.append(
                    _ModelFieldSpec(
                        name=name,
                        annotation=annotation,
                        required=required,
                        default=default,
                        description=description,
                    )
                )
            return result

        if self._is_plain_class_model(model_type):
            result = []
            class_docs = self._parse_docstring_args(model_type.__doc__)
            cls_info = Class(
                model_type,
                init=True,
                public=True,
                inherited=True,
                static_methods=True,
                protected=False,
                private=False,
                classmethod=True,
            )
            init_method = cls_info.init_method
            if init_method is None:
                return []
            for param in init_method.params:
                if param.kind in (InspectParameter.VAR_POSITIONAL, InspectParameter.VAR_KEYWORD):
                    continue
                annotation = param.type if param.is_typed else None
                description = param.description or class_docs.get(param.name)
                default = param.default if param.has_default else None
                result.append(
                    _ModelFieldSpec(
                        name=param.name,
                        annotation=annotation,
                        required=param.is_required,
                        default=default,
                        description=description,
                    )
                )
            return result

        return []

    def _parse_docstring_args(self, docstring: str | None) -> dict[str, str]:
        if not docstring:
            return {}

        import docstring_parser

        parsed = docstring_parser.parse(docstring)
        return {
            param.arg_name: (param.description or "").strip()
            for param in parsed.params
            if param.arg_name
        }

    def _expand_model_parameter(
        self,
        *,
        param: Parameter,
        model_type: type,
        is_optional_model: bool,
        taken_flags: list[str],
    ) -> list[Argument]:
        translated_name = self.parser.flag_strategy.argument_translator.translate(param.name)
        if translated_name in taken_flags:
            raise ReservedFlagError(translated_name)
        taken_flags.append(translated_name)

        model_default = param.default if param.has_default else MODEL_DEFAULT_UNSET
        max_depth = getattr(self.parser, "model_expansion_max_depth", 3)
        return self._expand_model_fields(
            model_type=model_type,
            root_name=param.name,
            path=(param.name,),
            taken_flags=taken_flags,
            depth=1,
            max_depth=max_depth,
            parent_optional=is_optional_model,
            parent_has_default=param.has_default,
            original_model_type=model_type,
            model_default=model_default,
        )

    def _expand_model_fields(
        self,
        *,
        model_type: type,
        root_name: str,
        path: tuple[str, ...],
        taken_flags: list[str],
        depth: int,
        max_depth: int,
        parent_optional: bool,
        parent_has_default: bool,
        original_model_type: type,
        model_default: Any,
    ) -> list[Argument]:
        nested_separator = self._nested_separator()
        arguments: list[Argument] = []
        for field in self._get_model_fields(model_type):
            annotation = resolve_type_alias(field.annotation)
            if isinstance(annotation, str):
                simple_name = simplified_type_name(annotation)
                base_name = simple_name[:-1] if simple_name.endswith("?") else simple_name
                builtin_map = {"bool": bool, "int": int, "float": float, "str": str}
                if base_name in builtin_map:
                    annotation = builtin_map[base_name]

            inner_type, is_optional_model = self._unwrap_optional(annotation)
            new_path = (*path, field.name)

            if self._should_expand_model(inner_type) and depth < max_depth:
                arguments.extend(
                    self._expand_model_fields(
                        model_type=inner_type,
                        root_name=root_name,
                        path=new_path,
                        taken_flags=taken_flags,
                        depth=depth + 1,
                        max_depth=max_depth,
                        parent_optional=parent_optional or is_optional_model,
                        parent_has_default=parent_has_default,
                        original_model_type=original_model_type,
                        model_default=model_default,
                    )
                )
                continue

            translated_path = tuple(
                self.parser.flag_strategy.argument_translator.translate(part) for part in new_path
            )
            display_name = nested_separator.join(translated_path)
            if display_name in taken_flags:
                raise ReservedFlagError(display_name)
            taken_flags.append(display_name)

            arg_name = nested_separator.join(new_path)
            flags = (f"--{display_name}",)

            is_required = field.required and not (
                parent_optional or is_optional_model or parent_has_default
            )
            spec = _ParamSpec(
                name=arg_name,
                type=annotation,
                is_typed=annotation is not None,
                has_default=not field.required,
                default=field.default,
                is_required=is_required,
                is_optional=is_optional_model,
                kind=InspectParameter.POSITIONAL_OR_KEYWORD,
                description=field.description,
            )

            spec.description = field.description or field.name

            arguments.append(
                self._argument_from_spec(
                    spec=spec,
                    translated_name=display_name,
                    flags=flags,
                    taken_flags=taken_flags,
                    pipe_param_names=None,
                    allow_optional_union_list=False,
                    suppress_default=True,
                    force_optional=False,
                    help_text=None,
                    is_expanded_from=root_name,
                    expansion_path=new_path,
                    original_model_type=original_model_type,
                    parent_is_optional=parent_optional,
                    model_default=model_default,
                )
            )

        return arguments

    def _argument_from_spec(
        self,
        *,
        spec: _ParamSpec,
        translated_name: str,
        flags: tuple[str, ...],
        taken_flags: list[str],
        pipe_param_names: set[str] | None,
        allow_optional_union_list: bool,
        suppress_default: bool,
        force_optional: bool = False,
        help_text: str | None = None,
        is_expanded_from: str | None = None,
        expansion_path: tuple[str, ...] = (),
        original_model_type: type | None = None,
        parent_is_optional: bool = False,
        model_default: Any = MODEL_DEFAULT_UNSET,
    ) -> Argument:
        if help_text is None:
            help_text = self.parser.help_layout.get_help_for_parameter(spec, tuple(flags))

        parser_func: Callable[[str], Any] | None = None
        value_shape = ValueShape.SINGLE
        nargs: str | int | None = None
        default_value: Any = spec.default if spec.has_default else None
        parsed_type: type[Any] | None = spec.type if spec.is_typed else None
        choices: tuple[Any, ...] | None = None
        if spec.is_typed and (raw_choices := get_param_choices(spec, for_display=False)):
            choices = tuple(raw_choices)
        boolean_behavior: BooleanBehavior | None = None
        is_optional_union_list = False
        tuple_element_parsers: tuple[Callable[[str], Any], ...] | None = None

        if spec.kind == InspectParameter.VAR_POSITIONAL:
            value_shape = ValueShape.LIST
            nargs = "*"
            default_value = ()  # Empty tuple as default for *args
            if spec.is_typed:
                parsed_type = spec.type
                if spec.type is not str:
                    parser_func = self.parser.type_parser.get_parse_func(spec.type)
        elif spec.is_typed:
            optional_union_list = extract_optional_union_list(spec.type)
            list_annotation: Any | None = None
            element_type: Any | None = None

            if optional_union_list:
                list_annotation, element_type = optional_union_list
                is_optional_union_list = True
            elif is_list_or_list_alias(spec.type):
                list_annotation = spec.type
                element_args = type_args(spec.type)
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

                if is_optional_union_list and not spec.has_default and allow_optional_union_list:
                    default_value = []

            elif is_fixed_tuple(spec.type):
                tuple_info = get_fixed_tuple_info(spec.type)
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

            elif spec.type is bool:
                value_shape = ValueShape.FLAG
                supports_negative = any(flag.startswith("--") for flag in flags)
                negative_form = None

                if supports_negative:
                    long_flags = [flag for flag in flags if flag.startswith("--")]
                    long_name = long_flags[0][2:] if long_flags else translated_name
                    negative_form = f"--{inverted_bool_flag_name(long_name)}"

                default_value = spec.default if spec.has_default else False

                boolean_behavior = BooleanBehavior(
                    supports_negative=supports_negative,
                    negative_form=negative_form,
                    default=default_value,
                )
            else:
                if spec.type is not str:
                    parser_func = self.parser.type_parser.get_parse_func(spec.type)

        if not spec.is_required and spec.is_typed and spec.type is not bool:
            default_value = spec.default

        metavar = None
        if self.parser.help_layout.clear_metavar and not spec.is_required:
            metavar = "\b"

        kind = ArgumentKind.POSITIONAL
        if any(flag.startswith("-") for flag in flags):
            kind = ArgumentKind.OPTION

        accepts_stdin = pipe_param_names is not None and spec.name in pipe_param_names
        pipe_required = accepts_stdin and spec.is_required

        if accepts_stdin:
            if (
                value_shape is ValueShape.SINGLE
                and kind is ArgumentKind.POSITIONAL
                and nargs is None
            ):
                nargs = "?"
            required = False
        else:
            if allow_optional_union_list:
                required = False if is_optional_union_list else spec.is_required
            else:
                required = spec.is_required

        if force_optional:
            required = False

        if suppress_default and not required:
            default_value = argparse.SUPPRESS
            if boolean_behavior is not None:
                boolean_behavior = BooleanBehavior(
                    supports_negative=boolean_behavior.supports_negative,
                    negative_form=boolean_behavior.negative_form,
                    default=argparse.SUPPRESS,
                )

        return Argument(
            name=spec.name,
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
            is_expanded_from=is_expanded_from,
            expansion_path=expansion_path,
            original_model_type=original_model_type,
            parent_is_optional=parent_is_optional,
            model_default=model_default,
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
                arg
                for param in obj.init_method.params
                for arg in self._argument_from_parameter(param, taken_flags, set())
            ]
        elif isinstance(obj, Function):
            self._prepare_layout_for_params(obj.params)
            return [
                arg
                for param in obj.params
                for arg in self._argument_from_parameter(param, taken_flags, set())
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
                arg
                for param in cls.get_method("__init__").params
                for arg in self._argument_from_parameter(param, taken_flags, set())
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


__all__ = ["ParserSchemaBuilder"]

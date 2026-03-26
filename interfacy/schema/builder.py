from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from dataclasses import MISSING, dataclass, fields, is_dataclass
from dataclasses import field as dataclass_field
from inspect import Parameter as InspectParameter
from inspect import _ParameterKind
from typing import TYPE_CHECKING, Any

from objinspect import Class, Function, Method, Parameter, inspect
from objinspect.typing import type_args

from interfacy.appearance.help_sort import (
    DEFAULT_HELP_OPTION_SORT_RULES,
    DEFAULT_HELP_SUBCOMMAND_SORT_RULES,
    HelpOptionSortRule,
    HelpSubcommandSortRule,
    resolve_help_option_sort_rules,
    resolve_help_subcommand_sort_rules,
)
from interfacy.exceptions import DuplicateCommandError, InvalidCommandError, ReservedFlagError
from interfacy.naming.flag_strategy import FlagAllocationState, get_arg_flags_for_parameter
from interfacy.pipe import PipeTargets
from interfacy.schema.model_argument_mapper import ModelArgumentMapper
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
    resolve_objinspect_annotations,
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
    kind: _ParameterKind
    description: str | None = None


@dataclass
class _ModelFieldSpec:
    name: str
    annotation: Any
    required: bool
    default: Any
    description: str | None = None


@dataclass
class _ArgumentBuildState:
    parser_func: Callable[[str], Any] | None
    value_shape: ValueShape
    nargs: str | int | None
    default_value: Any
    parsed_type: type[Any] | None
    choices: tuple[Any, ...] | None
    boolean_behavior: BooleanBehavior | None
    is_optional_union_list: bool = False
    tuple_element_parsers: tuple[Callable[[str], Any], ...] | None = None


@dataclass(frozen=True)
class _CommandBuildSettings:
    include_inherited_methods: bool
    include_classmethods: bool
    expand_model_params: bool
    model_expansion_max_depth: int
    abbreviation_scope: str
    help_option_sort: list[HelpOptionSortRule]
    help_subcommand_sort: list[HelpSubcommandSortRule]


OBJINSPECT_CLASS_ERRORS = (AttributeError, TypeError, ValueError)
_ABBREVIATION_SCOPE_ALL_OPTIONS = "all_options"


@dataclass
class ParserSchemaBuilder:
    """
    Build parser schemas from inspected commands.

    Attributes:
        parser (InterfacyParser): Source parser providing commands and layout settings.
    """

    parser: InterfacyParser
    model_argument_mapper: ModelArgumentMapper = dataclass_field(
        default_factory=ModelArgumentMapper
    )

    def _resolve_help_option_sort_value(
        self,
        value: object,
        *,
        value_name: str,
    ) -> list[HelpOptionSortRule]:
        rules = resolve_help_option_sort_rules(value, value_name=value_name)
        if rules:
            return list(rules)

        layout = self.parser.help_layout
        if layout is not None:
            layout_default = getattr(layout, "help_option_sort_default", None)
            layout_rules = resolve_help_option_sort_rules(
                layout_default,
                value_name=f"{layout.__class__.__name__}.help_option_sort_default",
            )
            if layout_rules:
                return list(layout_rules)

        return list(DEFAULT_HELP_OPTION_SORT_RULES)

    def _resolve_help_subcommand_sort_value(
        self,
        value: object,
        *,
        value_name: str,
    ) -> list[HelpSubcommandSortRule]:
        rules = resolve_help_subcommand_sort_rules(value, value_name=value_name)
        if rules:
            return list(rules)

        layout = self.parser.help_layout
        if layout is not None:
            layout_default = getattr(layout, "help_subcommand_sort_default", None)
            layout_rules = resolve_help_subcommand_sort_rules(
                layout_default,
                value_name=f"{layout.__class__.__name__}.help_subcommand_sort_default",
            )
            if layout_rules:
                return list(layout_rules)

        return list(DEFAULT_HELP_SUBCOMMAND_SORT_RULES)

    def _base_build_settings(self) -> _CommandBuildSettings:
        help_option_sort = self._resolve_help_option_sort_value(
            getattr(self.parser, "help_option_sort", None),
            value_name="help_option_sort",
        )
        help_subcommand_sort = self._resolve_help_subcommand_sort_value(
            getattr(self.parser, "help_subcommand_sort", None),
            value_name="help_subcommand_sort",
        )
        return _CommandBuildSettings(
            include_inherited_methods=getattr(self.parser, "include_inherited_methods", False),
            include_classmethods=getattr(self.parser, "include_classmethods", False),
            expand_model_params=getattr(self.parser, "expand_model_params", True),
            model_expansion_max_depth=getattr(self.parser, "model_expansion_max_depth", 3),
            abbreviation_scope=getattr(self.parser, "abbreviation_scope", "top_level_options"),
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
        )

    def _merge_build_settings(
        self,
        parent: _CommandBuildSettings | None,
        *,
        include_inherited_methods: bool | None = None,
        include_classmethods: bool | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: str | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
    ) -> _CommandBuildSettings:
        base = parent or self._base_build_settings()
        return _CommandBuildSettings(
            include_inherited_methods=(
                include_inherited_methods
                if include_inherited_methods is not None
                else base.include_inherited_methods
            ),
            include_classmethods=(
                include_classmethods
                if include_classmethods is not None
                else base.include_classmethods
            ),
            expand_model_params=(
                expand_model_params if expand_model_params is not None else base.expand_model_params
            ),
            model_expansion_max_depth=(
                model_expansion_max_depth
                if model_expansion_max_depth is not None
                else base.model_expansion_max_depth
            ),
            abbreviation_scope=(
                abbreviation_scope if abbreviation_scope is not None else base.abbreviation_scope
            ),
            help_option_sort=(
                list(help_option_sort)
                if help_option_sort is not None
                else list(base.help_option_sort)
            ),
            help_subcommand_sort=(
                list(help_subcommand_sort)
                if help_subcommand_sort is not None
                else list(base.help_subcommand_sort)
            ),
        )

    @staticmethod
    def _attach_command_build_settings(
        command: Command,
        *,
        settings: _CommandBuildSettings,
        include_inherited_methods: bool | None = None,
        include_classmethods: bool | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: str | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
    ) -> None:
        command.include_inherited_methods = include_inherited_methods
        command.include_classmethods = include_classmethods
        command.expand_model_params = expand_model_params
        command.model_expansion_max_depth = model_expansion_max_depth
        command.abbreviation_scope = abbreviation_scope
        command.help_option_sort = list(help_option_sort) if help_option_sort is not None else None
        command.help_subcommand_sort = (
            list(help_subcommand_sort) if help_subcommand_sort is not None else None
        )
        command.help_group = help_group
        command.help_option_sort_effective = list(settings.help_option_sort)
        command.help_subcommand_sort_effective = list(settings.help_subcommand_sort)

    def build(self) -> ParserSchema:
        """Build a ParserSchema for all registered commands."""
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
                    parent_settings=None,
                    include_inherited_methods=command.include_inherited_methods,
                    include_classmethods=command.include_classmethods,
                    expand_model_params=command.expand_model_params,
                    model_expansion_max_depth=(command.model_expansion_max_depth),
                    abbreviation_scope=command.abbreviation_scope,
                    help_option_sort=command.help_option_sort,
                    help_subcommand_sort=command.help_subcommand_sort,
                    help_group=command.help_group,
                )
                commands[canonical_name] = rebuilt

        commands_help = None
        if len(commands) > 1:
            commands_help = self._get_help_for_multiple_commands(commands)

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
        except (AttributeError, TypeError, ValueError):
            return

    def _get_help_for_class(
        self,
        cls: Class,
        *,
        rules: list[HelpSubcommandSortRule],
    ) -> str:
        try:
            return self.parser.help_layout.get_help_for_class(cls, rules=rules)
        except TypeError:
            return self.parser.help_layout.get_help_for_class(cls)

    def _get_help_for_multiple_commands(
        self,
        commands: dict[str, Command],
        *,
        rules: list[HelpSubcommandSortRule] | None = None,
    ) -> str:
        if rules is None:
            return self.parser.help_layout.get_help_for_multiple_commands(commands)
        try:
            return self.parser.help_layout.get_help_for_multiple_commands(commands, rules=rules)
        except TypeError:
            return self.parser.help_layout.get_help_for_multiple_commands(commands)

    def build_command_spec_for(
        self,
        obj: Class | Function | Method,
        *,
        canonical_name: str,
        description: str | None = None,
        aliases: tuple[str, ...] = (),
        parent_settings: _CommandBuildSettings | None = None,
        include_inherited_methods: bool | None = None,
        include_classmethods: bool | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: str | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
    ) -> Command:
        """
        Build a Command schema for a callable or class.

        Args:
            obj (Class | Function | Method): Inspected target to convert.
            canonical_name (str): Canonical command name.
            description (str | None): Optional description override.
            aliases (tuple[str, ...]): Alternate command names.
            parent_settings (_CommandBuildSettings | None): Parent effective settings.
            include_inherited_methods (bool | None): Per-command inherited-method override.
            include_classmethods (bool | None): Per-command classmethod override.
            expand_model_params (bool | None): Per-command model expansion override.
            model_expansion_max_depth (int | None): Per-command depth override.
            abbreviation_scope (str | None): Per-command abbreviation scope override.
            help_option_sort (list[HelpOptionSortRule] | None): Per-command option rules.
            help_subcommand_sort (list[HelpSubcommandSortRule] | None): Per-command
                subcommand rules.
            help_group (str | None): Optional help-only command group heading.
        """
        settings = self._merge_build_settings(
            parent_settings,
            include_inherited_methods=include_inherited_methods,
            include_classmethods=include_classmethods,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=model_expansion_max_depth,
            abbreviation_scope=abbreviation_scope,
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
        )
        resolve_objinspect_annotations(obj)
        if isinstance(obj, Function):
            return self._function_spec(
                obj,
                canonical_name=canonical_name,
                description=description,
                aliases=aliases,
                settings=settings,
                include_inherited_methods=include_inherited_methods,
                include_classmethods=include_classmethods,
                expand_model_params=expand_model_params,
                model_expansion_max_depth=model_expansion_max_depth,
                abbreviation_scope=abbreviation_scope,
                help_option_sort=help_option_sort,
                help_subcommand_sort=help_subcommand_sort,
                help_group=help_group,
            )

        if isinstance(obj, Method):
            return self._method_command(
                obj,
                canonical_name=canonical_name,
                description=description,
                aliases=aliases,
                settings=settings,
                include_inherited_methods=include_inherited_methods,
                include_classmethods=include_classmethods,
                expand_model_params=expand_model_params,
                model_expansion_max_depth=model_expansion_max_depth,
                abbreviation_scope=abbreviation_scope,
                help_option_sort=help_option_sort,
                help_subcommand_sort=help_subcommand_sort,
                help_group=help_group,
            )

        if isinstance(obj, Class):
            return self._class_command(
                obj,
                canonical_name=canonical_name,
                description=description,
                aliases=aliases,
                settings=settings,
                include_inherited_methods=include_inherited_methods,
                include_classmethods=include_classmethods,
                expand_model_params=expand_model_params,
                model_expansion_max_depth=model_expansion_max_depth,
                abbreviation_scope=abbreviation_scope,
                help_option_sort=help_option_sort,
                help_subcommand_sort=help_subcommand_sort,
                help_group=help_group,
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
        settings: _CommandBuildSettings | None = None,
        include_inherited_methods: bool | None = None,
        include_classmethods: bool | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: str | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
    ) -> Command:
        resolved_settings = settings or self._base_build_settings()
        taken_flags = [*self.parser.RESERVED_FLAGS]
        flag_state = FlagAllocationState()
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
            for arg in self._argument_from_parameter(
                param,
                taken_flags,
                pipe_param_names,
                settings=resolved_settings,
                flag_allocation_state=flag_state,
            )
        ]
        raw_description = description or (function.description if function.has_docstring else None)
        cli_name = self._resolve_cli_name(
            override=cli_name_override,
            canonical_name=canonical_name,
            fallback=function.name,
        )

        command = Command(
            obj=function,
            canonical_name=self._resolve_cli_name(None, canonical_name, function.name),
            cli_name=cli_name,
            aliases=aliases,
            raw_description=raw_description,
            help_group=help_group,
            parameters=parameters,
            pipe_targets=pipe_config,
            help_layout=self.parser.help_layout,
        )
        self._attach_command_build_settings(
            command,
            settings=resolved_settings,
            include_inherited_methods=include_inherited_methods,
            include_classmethods=include_classmethods,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=model_expansion_max_depth,
            abbreviation_scope=abbreviation_scope,
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
            help_group=help_group,
        )
        return command

    def _method_command(
        self,
        method: Method,
        *,
        canonical_name: str | None = None,
        description: str | None = None,
        aliases: tuple[str, ...] = (),
        settings: _CommandBuildSettings | None = None,
        include_inherited_methods: bool | None = None,
        include_classmethods: bool | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: str | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
    ) -> Command:
        resolved_settings = settings or self._base_build_settings()
        taken_flags = [*self.parser.RESERVED_FLAGS]
        init_flag_state = FlagAllocationState()
        method_flag_state = FlagAllocationState()

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
                for arg in self._argument_from_parameter(
                    param,
                    taken_flags,
                    init_pipe_names,
                    settings=resolved_settings,
                    flag_allocation_state=init_flag_state,
                )
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
            for arg in self._argument_from_parameter(
                param,
                taken_flags,
                pipe_param_names,
                settings=resolved_settings,
                flag_allocation_state=method_flag_state,
            )
        ]

        raw_description = description or (method.description if method.has_docstring else None)
        cli_name = self._resolve_cli_name(None, canonical_name, method.name)

        command = Command(
            obj=method,
            canonical_name=cli_name,
            cli_name=cli_name,
            aliases=aliases,
            raw_description=raw_description,
            help_group=help_group,
            parameters=parameters,
            initializer=initializer,
            pipe_targets=method_pipe_config,
            help_layout=self.parser.help_layout,
        )
        self._attach_command_build_settings(
            command,
            settings=resolved_settings,
            include_inherited_methods=include_inherited_methods,
            include_classmethods=include_classmethods,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=model_expansion_max_depth,
            abbreviation_scope=abbreviation_scope,
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
            help_group=help_group,
        )
        return command

    def _class_command(
        self,
        cls: Class,
        *,
        canonical_name: str | None = None,
        description: str | None = None,
        aliases: tuple[str, ...] = (),
        settings: _CommandBuildSettings | None = None,
        include_inherited_methods: bool | None = None,
        include_classmethods: bool | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: str | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
    ) -> Command:
        resolved_settings = settings or self._base_build_settings()
        taken_flags = [*self.parser.RESERVED_FLAGS]
        command_key = self.parser.COMMAND_KEY
        if command_key:
            taken_flags.append(command_key)
        init_flag_state = FlagAllocationState()

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
                for arg in self._argument_from_parameter(
                    param,
                    taken_flags,
                    init_pipe_names,
                    settings=resolved_settings,
                    flag_allocation_state=init_flag_state,
                )
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
                settings=resolved_settings,
            )

        raw_description = description or (cls.description if cls.has_docstring else None)
        cli_name = self._resolve_cli_name(None, canonical_name, cls.name)

        command = Command(
            obj=cls,
            canonical_name=cli_name,
            cli_name=cli_name,
            aliases=aliases,
            raw_description=raw_description,
            help_group=help_group,
            parameters=[],
            initializer=initializer,
            subcommands=subcommands,
            raw_epilog=self._get_help_for_class(
                cls,
                rules=resolved_settings.help_subcommand_sort,
            ),
            pipe_targets=class_pipe_config,
            help_layout=self.parser.help_layout,
        )
        self._attach_command_build_settings(
            command,
            settings=resolved_settings,
            include_inherited_methods=include_inherited_methods,
            include_classmethods=include_classmethods,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=model_expansion_max_depth,
            abbreviation_scope=abbreviation_scope,
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
            help_group=help_group,
        )
        return command

    def _argument_from_parameter(
        self,
        param: Parameter,
        taken_flags: list[str],
        pipe_param_names: set[str] | None = None,
        *,
        settings: _CommandBuildSettings | None = None,
        flag_allocation_state: FlagAllocationState | None = None,
    ) -> list[Argument]:
        resolved_settings = settings or self._base_build_settings()
        annotation = resolve_type_alias(param.type)
        if isinstance(annotation, str):
            simple_name = simplified_type_name(annotation)
            base_name = simple_name.removesuffix("?")
            builtin_map = {"bool": bool, "int": int, "float": float, "str": str}
            if base_name in builtin_map:
                annotation = builtin_map[base_name]

        if param.is_typed:
            model_type, is_optional_model = self.model_argument_mapper.unwrap_optional(annotation)
            if self._should_expand_model(model_type, settings=resolved_settings):
                return self._expand_model_parameter(
                    param=param,
                    model_type=model_type,
                    is_optional_model=is_optional_model,
                    taken_flags=taken_flags,
                    settings=resolved_settings,
                )

        translated_name = self.parser.flag_strategy.argument_translator.translate(param.name)
        if translated_name in taken_flags:
            raise ReservedFlagError(translated_name)

        flags = get_arg_flags_for_parameter(
            self.parser.flag_strategy,
            translated_name,
            param,
            taken_flags,
            self.parser.abbreviation_gen,
            allocation_state=flag_allocation_state,
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
                settings=resolved_settings,
            )
        ]

    @property
    def _nested_separator(self) -> str:
        return getattr(self.parser.flag_strategy, "nested_separator", ".")

    def _should_expand_model(
        self,
        param_type: object,
        *,
        settings: _CommandBuildSettings,
    ) -> bool:
        return self.model_argument_mapper.should_expand_model(
            param_type,
            expand_model_params=settings.expand_model_params,
        )

    def _get_model_fields(self, model_type: type) -> list[_ModelFieldSpec]:
        if is_dataclass(model_type):
            return self._get_dataclass_model_fields(model_type)
        if hasattr(model_type, "model_fields"):
            return self._get_pydantic_v2_model_fields(model_type)
        if hasattr(model_type, "__fields__"):
            return self._get_pydantic_v1_model_fields(model_type)
        if self.model_argument_mapper.is_plain_class_model(model_type):
            return self._get_plain_class_model_fields(model_type)
        return []

    def _get_dataclass_model_fields(self, model_type: type) -> list[_ModelFieldSpec]:
        arg_docs = self._parse_docstring_args(model_type.__doc__)
        result: list[_ModelFieldSpec] = []
        for field_info in fields(model_type):
            required = field_info.default is MISSING and field_info.default_factory is MISSING
            default = None
            if field_info.default is not MISSING:
                default = field_info.default
            elif field_info.default_factory is not MISSING:
                default = field_info.default_factory

            description = None
            if isinstance(field_info.metadata, Mapping):
                description = field_info.metadata.get("description") or field_info.metadata.get(
                    "help"
                )
            if description is None:
                description = arg_docs.get(field_info.name)

            result.append(
                _ModelFieldSpec(
                    name=field_info.name,
                    annotation=field_info.type,
                    required=required,
                    default=default,
                    description=description,
                )
            )
        return result

    def _get_pydantic_v2_model_fields(self, model_type: type) -> list[_ModelFieldSpec]:
        result: list[_ModelFieldSpec] = []
        field_map = getattr(model_type, "model_fields", {}) or {}
        for name, info in field_map.items():
            annotation = getattr(info, "annotation", None)
            if annotation is None and hasattr(model_type, "__annotations__"):
                annotation = model_type.__annotations__.get(name)

            required = False
            if hasattr(info, "is_required"):
                try:
                    required = bool(info.is_required())
                except TypeError:
                    required = bool(info.is_required)

            default = getattr(info, "default", None)
            if required:
                default = None

            result.append(
                _ModelFieldSpec(
                    name=name,
                    annotation=annotation,
                    required=required,
                    default=default,
                    description=getattr(info, "description", None),
                )
            )
        return result

    def _get_pydantic_v1_model_fields(self, model_type: type) -> list[_ModelFieldSpec]:
        result: list[_ModelFieldSpec] = []
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

    def _get_plain_class_model_fields(self, model_type: type) -> list[_ModelFieldSpec]:
        class_docs = self._parse_docstring_args(model_type.__doc__)
        try:
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
        except OBJINSPECT_CLASS_ERRORS:
            return []

        init_method = cls_info.init_method
        if init_method is None:
            return []

        result: list[_ModelFieldSpec] = []
        for param in init_method.params:
            if param.kind in (InspectParameter.VAR_POSITIONAL, InspectParameter.VAR_KEYWORD):
                continue
            annotation = param.type if param.is_typed else None
            result.append(
                _ModelFieldSpec(
                    name=param.name,
                    annotation=annotation,
                    required=param.is_required,
                    default=param.default if param.has_default else None,
                    description=param.description or class_docs.get(param.name),
                )
            )
        return result

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
        settings: _CommandBuildSettings,
    ) -> list[Argument]:
        translated_name = self.parser.flag_strategy.argument_translator.translate(param.name)
        if translated_name in taken_flags:
            raise ReservedFlagError(translated_name)
        taken_flags.append(translated_name)

        model_default = param.default if param.has_default else MODEL_DEFAULT_UNSET
        max_depth = settings.model_expansion_max_depth
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
            settings=settings,
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
        model_default: object,
        settings: _CommandBuildSettings,
    ) -> list[Argument]:
        nested_separator = self._nested_separator
        arguments: list[Argument] = []
        for field in self._get_model_fields(model_type):
            annotation = resolve_type_alias(field.annotation)
            if isinstance(annotation, str):
                simple_name = simplified_type_name(annotation)
                base_name = simple_name.removesuffix("?")
                builtin_map = {"bool": bool, "int": int, "float": float, "str": str}
                if base_name in builtin_map:
                    annotation = builtin_map[base_name]

            inner_type, is_optional_model = self.model_argument_mapper.unwrap_optional(annotation)
            new_path = (*path, field.name)

            if self._should_expand_model(inner_type, settings=settings) and depth < max_depth:
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
                        settings=settings,
                    )
                )
                continue

            translated_path = tuple(
                self.parser.flag_strategy.argument_translator.translate(part) for part in new_path
            )
            display_name = nested_separator.join(translated_path)
            if display_name in taken_flags:
                raise ReservedFlagError(display_name)

            arg_name = nested_separator.join(new_path)
            flags = self._expanded_option_flags(
                display_name=display_name,
                annotation=annotation,
                field_default=field.default,
                taken_flags=taken_flags,
                settings=settings,
            )
            taken_flags.append(display_name)

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
                    settings=settings,
                )
            )

        return arguments

    def _expanded_option_flags(
        self,
        *,
        display_name: str,
        annotation: object,
        field_default: object,
        taken_flags: list[str],
        settings: _CommandBuildSettings,
    ) -> tuple[str, ...]:
        long_flag = f"--{display_name}"
        flags: tuple[str, ...] = (long_flag,)
        abbreviation_scope = settings.abbreviation_scope
        if abbreviation_scope != _ABBREVIATION_SCOPE_ALL_OPTIONS:
            return flags

        abbrev_name = display_name
        is_bool = annotation is bool
        if is_bool and field_default is True:
            abbrev_name = f"no-{display_name}"

        short = self.parser.abbreviation_gen.generate(abbrev_name, taken_flags)
        if short and short not in (display_name, abbrev_name):
            return (f"-{short}", long_flag)

        return flags

    def _argument_from_spec(
        self,
        *,
        spec: _ParamSpec,
        translated_name: str,
        flags: tuple[str, ...],
        taken_flags: list[str],  # noqa: ARG002 - retained for keyword compatibility
        pipe_param_names: set[str] | None,
        allow_optional_union_list: bool,
        suppress_default: bool,
        force_optional: bool = False,
        help_text: str | None = None,
        is_expanded_from: str | None = None,
        expansion_path: tuple[str, ...] = (),
        original_model_type: type | None = None,
        parent_is_optional: bool = False,
        model_default: object = MODEL_DEFAULT_UNSET,
        settings: _CommandBuildSettings,  # noqa: ARG002 - retained for keyword compatibility
    ) -> Argument:
        resolved_help_text = help_text if help_text is not None else spec.description
        state = self._initial_argument_state(spec)

        if spec.kind == InspectParameter.VAR_POSITIONAL:
            self._configure_var_positional_state(spec, state)
        elif spec.is_typed:
            self._configure_typed_argument_state(
                spec=spec,
                flags=flags,
                translated_name=translated_name,
                allow_optional_union_list=allow_optional_union_list,
                state=state,
            )

        if not spec.is_required and spec.is_typed and spec.type is not bool:
            state.default_value = spec.default

        kind = self._argument_kind_from_flags(flags)
        accepts_stdin = pipe_param_names is not None and spec.name in pipe_param_names
        pipe_required = accepts_stdin and spec.is_required
        required = self._required_for_spec(
            spec=spec,
            allow_optional_union_list=allow_optional_union_list,
            accepts_stdin=accepts_stdin,
            kind=kind,
            state=state,
        )
        if force_optional:
            required = False

        self._apply_suppressed_default(
            state=state,
            suppress_default=suppress_default,
            required=required,
        )

        return Argument(
            name=spec.name,
            display_name=translated_name,
            kind=kind,
            value_shape=state.value_shape,
            flags=flags,
            required=required,
            default=state.default_value,
            help=resolved_help_text,
            type=state.parsed_type,
            parser=state.parser_func,
            metavar=self._metavar_for_spec(spec),
            nargs=state.nargs,
            boolean_behavior=state.boolean_behavior,
            choices=state.choices,
            accepts_stdin=accepts_stdin,
            pipe_required=pipe_required,
            tuple_element_parsers=state.tuple_element_parsers,
            is_expanded_from=is_expanded_from,
            expansion_path=expansion_path,
            original_model_type=original_model_type,
            parent_is_optional=parent_is_optional,
            model_default=model_default,
        )

    def _initial_argument_state(self, spec: _ParamSpec) -> _ArgumentBuildState:
        choices: tuple[Any, ...] | None = None
        if spec.is_typed and (raw_choices := get_param_choices(spec, for_display=False)):
            choices = tuple(raw_choices)
        return _ArgumentBuildState(
            parser_func=None,
            value_shape=ValueShape.SINGLE,
            nargs=None,
            default_value=spec.default if spec.has_default else None,
            parsed_type=spec.type if spec.is_typed else None,
            choices=choices,
            boolean_behavior=None,
        )

    def _configure_var_positional_state(
        self,
        spec: _ParamSpec,
        state: _ArgumentBuildState,
    ) -> None:
        state.value_shape = ValueShape.LIST
        state.nargs = "*"
        state.default_value = ()
        if spec.is_typed:
            state.parsed_type = spec.type
            if spec.type is not str:
                state.parser_func = self.parser.type_parser.get_parse_func(spec.type)

    def _configure_typed_argument_state(
        self,
        *,
        spec: _ParamSpec,
        flags: tuple[str, ...],
        translated_name: str,
        allow_optional_union_list: bool,
        state: _ArgumentBuildState,
    ) -> None:
        if self._configure_list_state(spec, allow_optional_union_list, state):
            return
        if self._configure_fixed_tuple_state(spec, state):
            return
        if self._configure_bool_state(spec, flags, translated_name, state):
            return
        self._configure_scalar_parser_state(spec, state)

    def _configure_list_state(
        self,
        spec: _ParamSpec,
        allow_optional_union_list: bool,
        state: _ArgumentBuildState,
    ) -> bool:
        optional_union_list = extract_optional_union_list(spec.type)
        list_annotation: Any | None = None
        element_type: Any | None = None

        if optional_union_list:
            list_annotation, element_type = optional_union_list
            state.is_optional_union_list = True
        elif is_list_or_list_alias(spec.type):
            list_annotation = spec.type
            element_args = type_args(spec.type)
            element_type = element_args[0] if element_args else None

        if list_annotation is None:
            return False

        state.value_shape = ValueShape.LIST
        list_is_effectively_optional = state.is_optional_union_list and allow_optional_union_list
        state.nargs = "+" if spec.is_required and not list_is_effectively_optional else "*"
        if element_type is not None:
            state.parsed_type = element_type
            if element_type is not str:
                state.parser_func = self.parser.type_parser.get_parse_func(element_type)
        else:
            state.parsed_type = None
            state.parser_func = None

        if state.is_optional_union_list and not spec.has_default and allow_optional_union_list:
            state.default_value = []
        return True

    def _configure_fixed_tuple_state(self, spec: _ParamSpec, state: _ArgumentBuildState) -> bool:
        if not is_fixed_tuple(spec.type):
            return False

        tuple_info = get_fixed_tuple_info(spec.type)
        if tuple_info is None:
            return True

        element_count, element_types = tuple_info
        state.value_shape = ValueShape.TUPLE
        state.nargs = element_count
        first_type = element_types[0]
        all_same_type = all(t == first_type for t in element_types)

        if all_same_type:
            state.parsed_type = first_type
            state.parser_func = self.parser.type_parser.get_parse_func(first_type)
        else:
            state.tuple_element_parsers = tuple(
                self.parser.type_parser.get_parse_func(t) for t in element_types
            )
            state.parsed_type = str
            state.parser_func = None
        return True

    def _configure_bool_state(
        self,
        spec: _ParamSpec,
        flags: tuple[str, ...],
        translated_name: str,
        state: _ArgumentBuildState,
    ) -> bool:
        if spec.type is not bool:
            return False

        state.value_shape = ValueShape.FLAG
        supports_negative = any(flag.startswith("--") for flag in flags)
        negative_form = None
        if supports_negative:
            long_flags = [flag for flag in flags if flag.startswith("--")]
            long_name = long_flags[0][2:] if long_flags else translated_name
            negative_form = f"--{inverted_bool_flag_name(long_name)}"

        state.default_value = spec.default if spec.has_default else False
        state.boolean_behavior = BooleanBehavior(
            supports_negative=supports_negative,
            negative_form=negative_form,
            default=state.default_value,
        )
        return True

    def _configure_scalar_parser_state(
        self,
        spec: _ParamSpec,
        state: _ArgumentBuildState,
    ) -> None:
        if spec.type is not str:
            state.parser_func = self.parser.type_parser.get_parse_func(spec.type)

    def _metavar_for_spec(self, spec: _ParamSpec) -> str | None:
        if self.parser.help_layout.clear_metavar and not spec.is_required:
            return "\b"
        return None

    def _argument_kind_from_flags(self, flags: tuple[str, ...]) -> ArgumentKind:
        if any(flag.startswith("-") for flag in flags):
            return ArgumentKind.OPTION
        return ArgumentKind.POSITIONAL

    def _required_for_spec(
        self,
        *,
        spec: _ParamSpec,
        allow_optional_union_list: bool,
        accepts_stdin: bool,
        kind: ArgumentKind,
        state: _ArgumentBuildState,
    ) -> bool:
        if accepts_stdin:
            if (
                state.value_shape is ValueShape.SINGLE
                and kind is ArgumentKind.POSITIONAL
                and state.nargs is None
            ):
                state.nargs = "?"
            elif state.value_shape is ValueShape.LIST and kind is ArgumentKind.POSITIONAL:
                state.nargs = "*"
            return False
        if allow_optional_union_list:
            return False if state.is_optional_union_list else spec.is_required
        return spec.is_required

    def _apply_suppressed_default(
        self,
        *,
        state: _ArgumentBuildState,
        suppress_default: bool,
        required: bool,
    ) -> None:
        if not (suppress_default and not required):
            return
        state.default_value = argparse.SUPPRESS
        if state.boolean_behavior is not None:
            state.boolean_behavior = BooleanBehavior(
                supports_negative=state.boolean_behavior.supports_negative,
                negative_form=state.boolean_behavior.negative_form,
                default=argparse.SUPPRESS,
            )

    def build_from_group(
        self,
        group: CommandGroup,
        parent_path: tuple[str, ...] = (),
        canonical_name: str | None = None,
        parent_settings: _CommandBuildSettings | None = None,
        include_inherited_methods: bool | None = None,
        include_classmethods: bool | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: str | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
    ) -> Command:
        """Build Command schema from a CommandGroup (manual construction)."""
        settings = self._merge_build_settings(
            parent_settings,
            include_inherited_methods=include_inherited_methods,
            include_classmethods=include_classmethods,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=model_expansion_max_depth,
            abbreviation_scope=abbreviation_scope,
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
        )
        cli_name = canonical_name or self.parser.flag_strategy.command_translator.translate(
            group.name
        )
        current_path = (*parent_path, cli_name)

        initializer: list[Argument] = []
        group_args_source = self._get_group_args_source(group)
        if group_args_source is not None:
            initializer = self._build_args_from_source(group_args_source, settings=settings)

        subcommands: dict[str, Command] = {}
        translated_child_names: set[str] = set()

        def register_translated_child(name: str, aliases: tuple[str, ...] = ()) -> None:
            cli_name = self.parser.flag_strategy.command_translator.translate(name)
            translated_aliases = tuple(
                self.parser.flag_strategy.command_translator.translate(alias) for alias in aliases
            )
            candidates = (cli_name, *translated_aliases)
            if len(set(candidates)) != len(candidates):
                raise DuplicateCommandError(cli_name)
            for candidate in candidates:
                if candidate in translated_child_names:
                    raise DuplicateCommandError(candidate)
            translated_child_names.update(candidates)

        for name, subgroup_entry in group.subgroup_entries.items():
            sub_cli_name = self.parser.flag_strategy.command_translator.translate(name)
            register_translated_child(name)
            subcommands[sub_cli_name] = self.build_from_group(
                subgroup_entry.group,
                current_path,
                parent_settings=settings,
                help_group=subgroup_entry.help_group,
            )

        for name, entry in group.commands.items():
            sub_cli_name = self.parser.flag_strategy.command_translator.translate(name)
            register_translated_child(name, entry.aliases)
            subcommands[sub_cli_name] = self._build_command_entry(
                entry,
                current_path,
                parent_settings=settings,
            )

        raw_epilog = None
        if subcommands:
            raw_epilog = self._build_group_epilog(
                subcommands,
                rules=settings.help_subcommand_sort,
            )

        command = Command(
            obj=None,
            canonical_name=cli_name,
            cli_name=cli_name,
            aliases=group.aliases,
            raw_description=group.description,
            help_group=help_group,
            parameters=[],
            initializer=initializer,
            subcommands=subcommands or None,
            raw_epilog=raw_epilog,
            help_layout=self.parser.help_layout,
            command_type="group",
            is_leaf=False,
            parent_path=parent_path,
        )
        self._attach_command_build_settings(
            command,
            settings=settings,
            include_inherited_methods=include_inherited_methods,
            include_classmethods=include_classmethods,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=model_expansion_max_depth,
            abbreviation_scope=abbreviation_scope,
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
            help_group=help_group,
        )
        return command

    def _get_group_args_source(self, group: CommandGroup) -> type | Callable[..., Any] | None:
        source = getattr(group, "group_args_source", None)
        if source is not None:
            return source
        return getattr(group, "_group_args_source", None)

    def _build_args_from_source(
        self,
        source: type | Callable[..., Any],
        *,
        settings: _CommandBuildSettings,
    ) -> list[Argument]:
        """Build argument list from a class __init__ or callable signature."""
        obj = inspect(source, init=True)
        resolve_objinspect_annotations(obj)
        taken_flags = [*self.parser.RESERVED_FLAGS]
        flag_state = FlagAllocationState()

        if isinstance(obj, Class) and obj.init_method:
            self._prepare_layout_for_params(obj.init_method.params)
            return [
                arg
                for param in obj.init_method.params
                for arg in self._argument_from_parameter(
                    param,
                    taken_flags,
                    set(),
                    settings=settings,
                    flag_allocation_state=flag_state,
                )
            ]
        if isinstance(obj, Function):
            self._prepare_layout_for_params(obj.params)
            return [
                arg
                for param in obj.params
                for arg in self._argument_from_parameter(
                    param,
                    taken_flags,
                    set(),
                    settings=settings,
                    flag_allocation_state=flag_state,
                )
            ]
        return []

    def _build_command_entry(
        self,
        entry: CommandEntry,
        parent_path: tuple[str, ...],
        *,
        parent_settings: _CommandBuildSettings,
    ) -> Command:
        """Build Command from a CommandEntry (function/class/instance)."""
        settings = self._merge_build_settings(
            parent_settings,
            include_inherited_methods=entry.include_inherited_methods,
            include_classmethods=entry.include_classmethods,
            expand_model_params=entry.expand_model_params,
            model_expansion_max_depth=entry.model_expansion_max_depth,
            abbreviation_scope=entry.abbreviation_scope,
            help_option_sort=entry.help_option_sort,
            help_subcommand_sort=entry.help_subcommand_sort,
        )
        if entry.is_instance:
            return self._build_from_instance(
                entry,
                parent_path,
                settings=settings,
                include_inherited_methods=entry.include_inherited_methods,
                include_classmethods=entry.include_classmethods,
                expand_model_params=entry.expand_model_params,
                model_expansion_max_depth=entry.model_expansion_max_depth,
                abbreviation_scope=entry.abbreviation_scope,
                help_option_sort=entry.help_option_sort,
                help_subcommand_sort=entry.help_subcommand_sort,
                help_group=entry.help_group,
            )
        if isinstance(entry.obj, type):
            return self._build_from_class_recursive(
                entry,
                parent_path,
                settings=settings,
                include_inherited_methods=entry.include_inherited_methods,
                include_classmethods=entry.include_classmethods,
                expand_model_params=entry.expand_model_params,
                model_expansion_max_depth=entry.model_expansion_max_depth,
                abbreviation_scope=entry.abbreviation_scope,
                help_option_sort=entry.help_option_sort,
                help_subcommand_sort=entry.help_subcommand_sort,
                help_group=entry.help_group,
            )
        obj = inspect(entry.obj)
        resolve_objinspect_annotations(obj)
        if isinstance(obj, (Function, Method)):
            cli_name = self.parser.flag_strategy.command_translator.translate(entry.name)
            return self._function_spec(
                obj,
                canonical_name=cli_name,
                description=entry.description,
                aliases=entry.aliases,
                settings=settings,
                include_inherited_methods=entry.include_inherited_methods,
                include_classmethods=entry.include_classmethods,
                expand_model_params=entry.expand_model_params,
                model_expansion_max_depth=entry.model_expansion_max_depth,
                abbreviation_scope=entry.abbreviation_scope,
                help_option_sort=entry.help_option_sort,
                help_subcommand_sort=entry.help_subcommand_sort,
                help_group=entry.help_group,
            )
        raise InvalidCommandError(entry.name)

    def _build_from_instance(
        self,
        entry: CommandEntry,
        parent_path: tuple[str, ...],
        *,
        settings: _CommandBuildSettings,
        include_inherited_methods: bool | None = None,
        include_classmethods: bool | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: str | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
    ) -> Command:
        """Build from a class instance - methods as commands, no __init__ args."""
        instance = entry.obj
        cls = inspect(
            type(instance),
            init=False,
            public=True,
            inherited=settings.include_inherited_methods,
            static_methods=True,
            classmethod=settings.include_classmethods,
        )
        assert isinstance(cls, Class)
        resolve_objinspect_annotations(cls)

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
                settings=settings,
            )

        cli_name = self.parser.flag_strategy.command_translator.translate(entry.name)
        raw_description = entry.description or (cls.description if cls.has_docstring else None)

        raw_epilog = None
        if subcommands:
            raw_epilog = self._build_group_epilog(
                subcommands,
                rules=settings.help_subcommand_sort,
            )

        command = Command(
            obj=cls,
            canonical_name=cli_name,
            cli_name=cli_name,
            aliases=entry.aliases,
            raw_description=raw_description,
            help_group=help_group,
            parameters=[],
            initializer=[],
            subcommands=subcommands or None,
            raw_epilog=raw_epilog,
            help_layout=self.parser.help_layout,
            command_type="instance",
            is_leaf=False,
            is_instance=True,
            parent_path=parent_path,
            stored_instance=instance,
        )
        self._attach_command_build_settings(
            command,
            settings=settings,
            include_inherited_methods=include_inherited_methods,
            include_classmethods=include_classmethods,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=model_expansion_max_depth,
            abbreviation_scope=abbreviation_scope,
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
            help_group=help_group,
        )
        return command

    def _build_from_class_recursive(
        self,
        entry: CommandEntry,
        parent_path: tuple[str, ...],
        *,
        settings: _CommandBuildSettings,
        include_inherited_methods: bool | None = None,
        include_classmethods: bool | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: str | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
    ) -> Command:
        """Build from a class - methods AND nested classes (recursive)."""
        from interfacy.group import CommandEntry

        cls = inspect(
            entry.obj,
            init=True,
            public=True,
            inherited=settings.include_inherited_methods,
            static_methods=True,
            classmethod=settings.include_classmethods,
        )
        assert isinstance(cls, Class)
        cli_name = self.parser.flag_strategy.command_translator.translate(entry.name)
        current_path = (*parent_path, cli_name)

        taken_flags = [*self.parser.RESERVED_FLAGS]
        command_key = self.parser.COMMAND_KEY
        if command_key:
            taken_flags.append(command_key)
        init_flag_state = FlagAllocationState()

        initializer: list[Argument] = []
        if cls.has_init and not cls.is_initialized:
            self._prepare_layout_for_params(cls.get_method("__init__").params)
            initializer = [
                arg
                for param in cls.get_method("__init__").params
                for arg in self._argument_from_parameter(
                    param,
                    taken_flags,
                    set(),
                    settings=settings,
                    flag_allocation_state=init_flag_state,
                )
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
                settings=settings,
            )

        for attr_name in dir(entry.obj):
            if attr_name.startswith("_"):
                continue
            attr = getattr(entry.obj, attr_name, None)
            if attr is None:
                continue
            if isinstance(attr, type):
                nested_entry = CommandEntry(
                    obj=attr,
                    name=attr_name,
                    description=None,
                    aliases=(),
                    is_instance=False,
                )
                nested_cli_name = self.parser.flag_strategy.command_translator.translate(attr_name)
                subcommands[nested_cli_name] = self._build_from_class_recursive(
                    nested_entry,
                    current_path,
                    settings=settings,
                )

        raw_description = entry.description or (cls.description if cls.has_docstring else None)

        raw_epilog = None
        if subcommands:
            raw_epilog = self._build_group_epilog(
                subcommands,
                rules=settings.help_subcommand_sort,
            )

        command = Command(
            obj=cls,
            canonical_name=cli_name,
            cli_name=cli_name,
            aliases=entry.aliases,
            raw_description=raw_description,
            help_group=help_group,
            parameters=[],
            initializer=initializer,
            subcommands=subcommands or None,
            raw_epilog=raw_epilog,
            help_layout=self.parser.help_layout,
            command_type="class",
            is_leaf=False,
            parent_path=parent_path,
        )
        self._attach_command_build_settings(
            command,
            settings=settings,
            include_inherited_methods=include_inherited_methods,
            include_classmethods=include_classmethods,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=model_expansion_max_depth,
            abbreviation_scope=abbreviation_scope,
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
            help_group=help_group,
        )
        return command

    def _build_group_epilog(
        self,
        subcommands: dict[str, Command],
        *,
        rules: list[HelpSubcommandSortRule],
    ) -> str:
        """Build epilog text listing available subcommands."""
        return self._get_help_for_multiple_commands(subcommands, rules=rules)

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

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
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
from interfacy.exceptions import (
    DuplicateCommandError,
    InvalidCommandError,
    ReservedFlagError,
)
from interfacy.executable_flag import ExecutableFlag, executable_flag_tokens
from interfacy.naming.flag_strategy import FlagAllocationState, get_arg_flags_for_parameter
from interfacy.pipe import PipeTargets
from interfacy.schema.model_argument_mapper import ModelArgumentMapper
from interfacy.schema.schema import (
    MODEL_DEFAULT_UNSET,
    Argument,
    ArgumentKind,
    BooleanBehavior,
    BooleanMode,
    Command,
    ParserSchema,
    ValueShape,
)
from interfacy.schema.value_plan import (
    ArgumentValue,
    FixedTupleValue,
    FlagValue,
    ObjectFieldValue,
    ObjectValue,
    RepeatedValue,
    ScalarValue,
    UntypedValue,
    plan_requires_post_conversion,
)
from interfacy.util import (
    extract_optional_union_list,
    extract_optional_union_tuple,
    extract_union_list,
    get_annotation_choices,
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
    from interfacy.appearance.layout import HelpLayout
    from interfacy.core import InterfacyParser
    from interfacy.group import CommandEntry, CommandGroup


@dataclass
class ParamSpec:
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
class ArgumentBuildState:
    parser_func: Callable[[str], Any] | None
    value_shape: ValueShape
    nargs: str | int | None
    default_value: Any
    parsed_type: type[Any] | None
    choices: tuple[Any, ...] | None
    boolean_behavior: BooleanBehavior | None
    is_optional_union_list: bool = False
    tuple_element_parsers: tuple[Callable[[str], Any], ...] | None = None
    value_plan: ArgumentValue | None = None


@dataclass(frozen=True)
class CommandBuildSettings:
    include_inherited_methods: bool
    include_protected_methods: bool
    include_private_methods: bool
    include_staticmethods: bool
    include_classmethods: bool
    method_skips: list[str]
    expand_model_params: bool
    model_expansion_max_depth: int
    abbreviation_scope: str
    help_option_sort: list[HelpOptionSortRule]
    help_subcommand_sort: list[HelpSubcommandSortRule]


@dataclass
class SchemaBuildContext:
    """Builder-owned Interface for parser state needed during schema construction."""

    source: InterfacyParser
    description: str | None
    epilog: str | None
    commands: dict[str, Command]
    command_key: str | None
    reserved_flags: list[str]
    method_skips: list[str]
    allow_args_from_file: bool
    pipe_targets_default: PipeTargets | None
    metadata: dict[str, Any]
    executable_flags: list[ExecutableFlag]
    help_layout: HelpLayout
    type_parser: Any
    flag_strategy: Any
    abbreviation_gen: Any
    include_inherited_methods: bool
    include_protected_methods: bool
    include_private_methods: bool
    include_staticmethods: bool
    include_classmethods: bool
    expand_model_params: bool
    model_expansion_max_depth: int
    abbreviation_scope: str
    help_option_sort: Any
    help_subcommand_sort: Any
    help_option_sort_effective: list[HelpOptionSortRule]
    help_subcommand_sort_effective: list[HelpSubcommandSortRule]
    bool_negative_prefix: str | None
    negative_bool_name_mode: str
    negative_bool_name_prefixes: tuple[str, ...]
    help_flags: tuple[str, ...]

    @classmethod
    def from_parser(cls, parser: InterfacyParser) -> SchemaBuildContext:
        return cls(
            source=parser,
            description=parser.description,
            epilog=parser.epilog,
            commands=parser.commands,
            command_key=parser.COMMAND_KEY,
            reserved_flags=list(parser.RESERVED_FLAGS),
            method_skips=list(parser.method_skips),
            allow_args_from_file=parser.allow_args_from_file,
            pipe_targets_default=parser.pipe_targets_default,
            metadata=dict(getattr(parser, "metadata", {})),
            executable_flags=list(getattr(parser, "executable_flags", [])),
            help_layout=parser.help_layout,
            type_parser=parser.type_parser,
            flag_strategy=parser.flag_strategy,
            abbreviation_gen=parser.abbreviation_gen,
            include_inherited_methods=parser.include_inherited_methods,
            include_protected_methods=parser.include_protected_methods,
            include_private_methods=parser.include_private_methods,
            include_staticmethods=parser.include_staticmethods,
            include_classmethods=parser.include_classmethods,
            expand_model_params=parser.expand_model_params,
            model_expansion_max_depth=parser.model_expansion_max_depth,
            abbreviation_scope=parser.abbreviation_scope,
            help_option_sort=parser.help_option_sort,
            help_subcommand_sort=parser.help_subcommand_sort,
            help_option_sort_effective=list(
                getattr(parser, "help_option_sort_effective", DEFAULT_HELP_OPTION_SORT_RULES)
            ),
            help_subcommand_sort_effective=list(
                getattr(
                    parser, "help_subcommand_sort_effective", DEFAULT_HELP_SUBCOMMAND_SORT_RULES
                )
            ),
            bool_negative_prefix=getattr(parser, "bool_negative_prefix", "no-"),
            negative_bool_name_mode=getattr(parser, "negative_bool_name_mode", "flag_only"),
            negative_bool_name_prefixes=tuple(
                getattr(parser, "negative_bool_name_prefixes", ("no-", "disable-", "without-"))
            ),
            help_flags=tuple(getattr(parser, "help_flags", ("--help",))),
        )

    def resolve_pipe_targets_by_names(
        self,
        *,
        canonical_name: str | None,
        obj_name: str | None,
        aliases: Iterable[str] | None,
        subcommand: str | None,
        include_default: bool,
    ) -> PipeTargets | None:
        return self.source.resolve_pipe_targets_by_names(
            canonical_name=canonical_name,
            obj_name=obj_name,
            aliases=aliases,
            subcommand=subcommand,
            include_default=include_default,
        )

    def transform_schema_with_plugins(self, schema: ParserSchema) -> ParserSchema:
        transform_schema = getattr(self.source, "_transform_schema_with_plugins", None)
        if callable(transform_schema):
            return transform_schema(schema)

        return schema


@dataclass
class CommandSchemaConstructor:
    """Build command schemas for callable, method, and class command shapes."""

    builder: ParserSchemaBuilder

    def build_command_spec_for(
        self,
        obj: Class | Function | Method,
        *,
        canonical_name: str,
        description: str | None = None,
        aliases: tuple[str, ...] = (),
        executable_flags: list[ExecutableFlag] | None = None,
        parent_settings: CommandBuildSettings | None = None,
        include_inherited_methods: bool | None = None,
        include_protected_methods: bool | None = None,
        include_private_methods: bool | None = None,
        include_staticmethods: bool | None = None,
        include_classmethods: bool | None = None,
        method_skips: Sequence[str] | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: str | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
    ) -> Command:
        settings = self.builder._merge_build_settings(
            parent_settings,
            include_inherited_methods=include_inherited_methods,
            include_protected_methods=include_protected_methods,
            include_private_methods=include_private_methods,
            include_staticmethods=include_staticmethods,
            include_classmethods=include_classmethods,
            method_skips=method_skips,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=model_expansion_max_depth,
            abbreviation_scope=abbreviation_scope,
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
        )
        resolve_objinspect_annotations(obj)

        if isinstance(obj, Function):
            return self.function_spec(
                obj,
                canonical_name=canonical_name,
                description=description,
                aliases=aliases,
                executable_flags=executable_flags,
                settings=settings,
                include_inherited_methods=include_inherited_methods,
                include_protected_methods=include_protected_methods,
                include_private_methods=include_private_methods,
                include_staticmethods=include_staticmethods,
                include_classmethods=include_classmethods,
                method_skips=method_skips,
                expand_model_params=expand_model_params,
                model_expansion_max_depth=model_expansion_max_depth,
                abbreviation_scope=abbreviation_scope,
                help_option_sort=help_option_sort,
                help_subcommand_sort=help_subcommand_sort,
                help_group=help_group,
            )
        if isinstance(obj, Method):
            return self.method_command(
                obj,
                canonical_name=canonical_name,
                description=description,
                aliases=aliases,
                executable_flags=executable_flags,
                settings=settings,
                include_inherited_methods=include_inherited_methods,
                include_protected_methods=include_protected_methods,
                include_private_methods=include_private_methods,
                include_staticmethods=include_staticmethods,
                include_classmethods=include_classmethods,
                method_skips=method_skips,
                expand_model_params=expand_model_params,
                model_expansion_max_depth=model_expansion_max_depth,
                abbreviation_scope=abbreviation_scope,
                help_option_sort=help_option_sort,
                help_subcommand_sort=help_subcommand_sort,
                help_group=help_group,
            )
        if isinstance(obj, Class):
            return self.class_command(
                obj,
                canonical_name=canonical_name,
                description=description,
                aliases=aliases,
                executable_flags=executable_flags,
                settings=settings,
                include_inherited_methods=include_inherited_methods,
                include_protected_methods=include_protected_methods,
                include_private_methods=include_private_methods,
                include_staticmethods=include_staticmethods,
                include_classmethods=include_classmethods,
                method_skips=method_skips,
                expand_model_params=expand_model_params,
                model_expansion_max_depth=model_expansion_max_depth,
                abbreviation_scope=abbreviation_scope,
                help_option_sort=help_option_sort,
                help_subcommand_sort=help_subcommand_sort,
                help_group=help_group,
            )

        raise InvalidCommandError(obj)

    def function_spec(self, function: Function | Method, **kwargs: Any) -> Command:
        return self.builder._function_spec(**{"function": function, **kwargs})

    def method_command(self, method: Method, **kwargs: Any) -> Command:
        return self.builder._method_command(**{"method": method, **kwargs})

    def class_command(self, cls: Class, **kwargs: Any) -> Command:
        return self.builder._class_command(**{"cls": cls, **kwargs})


_ABBREVIATION_SCOPE_ALL_OPTIONS = "all_options"


@dataclass
class ExpansionParameter:
    name: str
    default: Any
    has_default: bool


@dataclass
class ModelExpansionBuilder:
    """Build expanded CLI arguments for one model parameter."""

    builder: ParserSchemaBuilder
    param: Parameter | ExpansionParameter
    taken_flags: list[str]
    settings: CommandBuildSettings

    @property
    def context(self) -> SchemaBuildContext:
        return self.builder.context

    @property
    def model_argument_mapper(self) -> ModelArgumentMapper:
        return self.builder.model_argument_mapper

    @property
    def nested_separator(self) -> str:
        return self.builder._nested_separator

    def build(self, *, model_type: type, is_optional_model: bool) -> list[Argument]:
        translated_name = self.context.flag_strategy.argument_translator.translate(self.param.name)
        if translated_name in self.taken_flags:
            raise ReservedFlagError(translated_name)

        self.taken_flags.append(translated_name)

        model_default = self.param.default if self.param.has_default else MODEL_DEFAULT_UNSET
        return self._fields(
            model_type=model_type,
            root_name=self.param.name,
            path=(self.param.name,),
            depth=1,
            parent_optional=is_optional_model,
            parent_has_default=self.param.has_default,
            original_model_type=model_type,
            model_default=model_default,
        )

    def _fields(
        self,
        *,
        model_type: type,
        root_name: str,
        path: tuple[str, ...],
        depth: int,
        parent_optional: bool,
        parent_has_default: bool,
        original_model_type: type,
        model_default: Any,
    ) -> list[Argument]:
        arguments: list[Argument] = []
        max_depth = self.settings.model_expansion_max_depth

        for field in self.model_argument_mapper.model_fields_for_expansion(model_type):
            annotation = self._normalize_annotation(field.annotation)
            inner_type, is_optional_model = self.model_argument_mapper.unwrap_optional(annotation)
            new_path = (*path, field.name)

            if self.builder._should_expand_model(inner_type, settings=self.settings) and (
                depth < max_depth
            ):
                arguments.extend(
                    self._fields(
                        model_type=inner_type,
                        root_name=root_name,
                        path=new_path,
                        depth=depth + 1,
                        parent_optional=parent_optional or is_optional_model,
                        parent_has_default=parent_has_default,
                        original_model_type=original_model_type,
                        model_default=model_default,
                    )
                )
                continue

            arguments.append(
                self._argument_for_field(
                    field=field,
                    annotation=annotation,
                    path=new_path,
                    root_name=root_name,
                    is_optional_model=is_optional_model,
                    parent_optional=parent_optional,
                    parent_has_default=parent_has_default,
                    original_model_type=original_model_type,
                    model_default=model_default,
                )
            )

        return arguments

    @staticmethod
    def _normalize_annotation(annotation: Any) -> Any:
        annotation = resolve_type_alias(annotation)
        if not isinstance(annotation, str):
            return annotation

        simple_name = simplified_type_name(annotation)
        base_name = simple_name.removesuffix("?")
        builtin_map = {"bool": bool, "int": int, "float": float, "str": str}

        return builtin_map.get(base_name, annotation)

    def _argument_for_field(
        self,
        *,
        field: Any,
        annotation: Any,
        path: tuple[str, ...],
        root_name: str,
        is_optional_model: bool,
        parent_optional: bool,
        parent_has_default: bool,
        original_model_type: type,
        model_default: Any,
    ) -> Argument:
        translated_path = tuple(
            self.context.flag_strategy.argument_translator.translate(part) for part in path
        )
        display_name = self.nested_separator.join(translated_path)
        if display_name in self.taken_flags:
            raise ReservedFlagError(display_name)

        arg_name = self.nested_separator.join(path)
        flags = self._option_flags(
            display_name=display_name,
            annotation=annotation,
            field_default=field.default,
        )
        self.taken_flags.append(display_name)

        is_required = field.required and not (
            parent_optional or is_optional_model or parent_has_default
        )
        spec = ParamSpec(
            name=arg_name,
            type=annotation,
            is_typed=annotation is not None,
            has_default=not field.required,
            default=field.default,
            is_required=is_required,
            is_optional=is_optional_model,
            kind=InspectParameter.POSITIONAL_OR_KEYWORD,
            description=field.description or field.name,
        )

        return self.builder._argument_from_spec(
            spec=spec,
            translated_name=display_name,
            flags=flags,
            taken_flags=self.taken_flags,
            pipe_param_names=None,
            allow_optional_union_list=False,
            suppress_default=True,
            force_optional=False,
            help_text=None,
            is_expanded_from=root_name,
            expansion_path=path,
            original_model_type=original_model_type,
            parent_is_optional=parent_optional,
            model_default=model_default,
            settings=self.settings,
        )

    def _option_flags(
        self,
        *,
        display_name: str,
        annotation: Any,
        field_default: Any,
    ) -> tuple[str, ...]:
        long_flag = f"--{display_name}"
        flags: tuple[str, ...] = (long_flag,)
        if self.settings.abbreviation_scope != _ABBREVIATION_SCOPE_ALL_OPTIONS:
            return flags

        abbrev_name = display_name
        if annotation is bool and field_default is True:
            abbrev_name = f"no-{display_name}"

        short = self.context.abbreviation_gen.generate(abbrev_name, self.taken_flags)
        if short and short not in (display_name, abbrev_name):
            return (f"-{short}", long_flag)

        return flags


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
    context: SchemaBuildContext = dataclass_field(init=False)
    command_constructor: CommandSchemaConstructor = dataclass_field(init=False)

    def __post_init__(self) -> None:
        self.context = SchemaBuildContext.from_parser(self.parser)
        self.command_constructor = CommandSchemaConstructor(self)

    def _resolve_help_option_sort_value(
        self,
        value: Any,
        *,
        value_name: str,
    ) -> list[HelpOptionSortRule]:
        rules = resolve_help_option_sort_rules(value, value_name=value_name)
        if rules:
            return list(rules)

        layout = self.context.help_layout
        if layout is not None:
            layout_rules = resolve_help_option_sort_rules(
                layout.help_option_sort_default,
                value_name=f"{layout.__class__.__name__}.help_option_sort_default",
            )
            if layout_rules:
                return list(layout_rules)

        return list(DEFAULT_HELP_OPTION_SORT_RULES)

    def _resolve_help_subcommand_sort_value(
        self,
        value: Any,
        *,
        value_name: str,
    ) -> list[HelpSubcommandSortRule]:
        rules = resolve_help_subcommand_sort_rules(value, value_name=value_name)
        if rules:
            return list(rules)

        layout = self.context.help_layout
        if layout is not None:
            layout_rules = resolve_help_subcommand_sort_rules(
                layout.help_subcommand_sort_default,
                value_name=f"{layout.__class__.__name__}.help_subcommand_sort_default",
            )
            if layout_rules:
                return list(layout_rules)

        return list(DEFAULT_HELP_SUBCOMMAND_SORT_RULES)

    def _base_build_settings(self) -> CommandBuildSettings:
        help_option_sort = self._resolve_help_option_sort_value(
            self.context.help_option_sort,
            value_name="help_option_sort",
        )
        help_subcommand_sort = self._resolve_help_subcommand_sort_value(
            self.context.help_subcommand_sort,
            value_name="help_subcommand_sort",
        )
        return CommandBuildSettings(
            include_inherited_methods=self.context.include_inherited_methods,
            include_protected_methods=self.context.include_protected_methods,
            include_private_methods=self.context.include_private_methods,
            include_staticmethods=self.context.include_staticmethods,
            include_classmethods=self.context.include_classmethods,
            method_skips=list(self.context.method_skips),
            expand_model_params=self.context.expand_model_params,
            model_expansion_max_depth=self.context.model_expansion_max_depth,
            abbreviation_scope=self.context.abbreviation_scope,
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
        )

    def _merge_build_settings(
        self,
        parent: CommandBuildSettings | None,
        *,
        include_inherited_methods: bool | None = None,
        include_protected_methods: bool | None = None,
        include_private_methods: bool | None = None,
        include_staticmethods: bool | None = None,
        include_classmethods: bool | None = None,
        method_skips: Sequence[str] | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: str | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
    ) -> CommandBuildSettings:
        base = parent or self._base_build_settings()
        return CommandBuildSettings(
            include_inherited_methods=(
                include_inherited_methods
                if include_inherited_methods is not None
                else base.include_inherited_methods
            ),
            include_protected_methods=(
                include_protected_methods
                if include_protected_methods is not None
                else base.include_protected_methods
            ),
            include_private_methods=(
                include_private_methods
                if include_private_methods is not None
                else base.include_private_methods
            ),
            include_staticmethods=(
                include_staticmethods
                if include_staticmethods is not None
                else base.include_staticmethods
            ),
            include_classmethods=(
                include_classmethods
                if include_classmethods is not None
                else base.include_classmethods
            ),
            method_skips=list(method_skips)
            if method_skips is not None
            else list(base.method_skips),
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
        settings: CommandBuildSettings,
        include_inherited_methods: bool | None = None,
        include_protected_methods: bool | None = None,
        include_private_methods: bool | None = None,
        include_staticmethods: bool | None = None,
        include_classmethods: bool | None = None,
        method_skips: Sequence[str] | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: str | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
    ) -> None:
        command.include_inherited_methods = include_inherited_methods
        command.include_protected_methods = include_protected_methods
        command.include_private_methods = include_private_methods
        command.include_staticmethods = include_staticmethods
        command.include_classmethods = include_classmethods
        command.method_skips = list(method_skips) if method_skips is not None else None
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
        for canonical_name, command in self.context.commands.items():
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
                    executable_flags=command.executable_flags,
                    parent_settings=None,
                    include_inherited_methods=command.include_inherited_methods,
                    include_protected_methods=command.include_protected_methods,
                    include_private_methods=command.include_private_methods,
                    include_staticmethods=command.include_staticmethods,
                    include_classmethods=command.include_classmethods,
                    method_skips=command.method_skips,
                    expand_model_params=command.expand_model_params,
                    model_expansion_max_depth=(command.model_expansion_max_depth),
                    abbreviation_scope=command.abbreviation_scope,
                    help_option_sort=command.help_option_sort,
                    help_subcommand_sort=command.help_subcommand_sort,
                    help_group=command.help_group,
                )
                commands[canonical_name] = rebuilt

        parser_executable_flags = list(getattr(self.context, "executable_flags", []))
        schema = ParserSchema(
            raw_description=self.context.description,
            raw_epilog=self.context.epilog,
            commands=commands,
            command_key=self.context.command_key,
            allow_args_from_file=self.context.allow_args_from_file,
            pipe_targets=self.context.pipe_targets_default,
            theme=self.context.help_layout,
            metadata=dict(getattr(self.context, "metadata", {})),
            executable_flags=parser_executable_flags,
            help_option_sort_effective=list(
                getattr(self.context, "help_option_sort_effective", [])
            ),
            help_flags=self.context.help_flags,
        )
        schema = self.context.transform_schema_with_plugins(schema)

        self._finalize_schema(schema)
        self._validate_executable_flags_against_tokens(parser_executable_flags, set())
        single_cmd = next(iter(schema.commands.values())) if len(schema.commands) == 1 else None
        if single_cmd is not None and single_cmd.is_leaf:
            self._validate_executable_flags_against_tokens(
                parser_executable_flags,
                self._command_option_strings(single_cmd),
            )
            self._validate_executable_flags_against_tokens(
                single_cmd.executable_flags,
                executable_flag_tokens(parser_executable_flags),
            )

        return schema

    @staticmethod
    def _invalidate_cached_help_values(target: Any) -> None:
        if hasattr(target, "__dict__"):
            target.__dict__.pop("description", None)
            target.__dict__.pop("epilog", None)

    def _finalize_schema(self, schema: ParserSchema) -> None:
        root_option_rules = list(
            schema.help_option_sort_effective
            or getattr(self.context, "help_option_sort_effective", DEFAULT_HELP_OPTION_SORT_RULES)
        )
        root_subcommand_rules = list(
            getattr(
                self.context, "help_subcommand_sort_effective", DEFAULT_HELP_SUBCOMMAND_SORT_RULES
            )
        )
        for command in schema.commands.values():
            self._finalize_command(
                command,
                default_layout=schema.theme,
                parent_option_rules=root_option_rules,
                parent_subcommand_rules=root_subcommand_rules,
            )

        schema.commands_help = (
            self._get_help_for_multiple_commands(schema.commands)
            if len(schema.commands) > 1
            else None
        )
        self._invalidate_cached_help_values(schema)

    def _finalize_command(
        self,
        command: Command,
        *,
        default_layout: HelpLayout | None,
        parent_option_rules: list[HelpOptionSortRule],
        parent_subcommand_rules: list[HelpSubcommandSortRule],
    ) -> None:
        if command.help_layout is None:
            command.help_layout = default_layout

        command.is_leaf = not bool(command.subcommands)
        if command.command_type == "group" and not command.subcommands:
            command.is_leaf = False

        command.help_option_sort_effective = list(
            command.help_option_sort
            if command.help_option_sort is not None
            else parent_option_rules
        )
        command.help_subcommand_sort_effective = list(
            command.help_subcommand_sort
            if command.help_subcommand_sort is not None
            else parent_subcommand_rules
        )

        if (
            command.subcommands
            and command.metadata.get("_interfacy_derived_epilog")
            and command.command_type != "class"
        ):
            command.raw_epilog = self._build_group_epilog(
                command.subcommands,
                rules=command.help_subcommand_sort_effective,
            )

        self._invalidate_cached_help_values(command)

        if not command.subcommands:
            return

        for subcommand in command.subcommands.values():
            self._finalize_command(
                subcommand,
                default_layout=command.help_layout or default_layout,
                parent_option_rules=command.help_option_sort_effective,
                parent_subcommand_rules=command.help_subcommand_sort_effective,
            )

    def _prepare_layout_for_params(self, params: list[Parameter]) -> None:
        if not params:
            return

        layout = self.context.help_layout
        if layout is None:
            return

        try:
            layout.prepare_default_field_width_for_params(params)
        except (AttributeError, TypeError, ValueError):
            return

    @staticmethod
    def _argument_option_strings(arguments: Sequence[Argument]) -> set[str]:
        option_strings: set[str] = set()
        for argument in arguments:
            if argument.kind is not ArgumentKind.OPTION:
                continue
            option_strings.update(flag for flag in argument.flags if flag.startswith("-"))

        return option_strings

    def _command_option_strings(self, command: Command) -> set[str]:
        option_strings = self._argument_option_strings([*command.initializer, *command.parameters])
        option_strings.update(executable_flag_tokens(command.executable_flags))
        return option_strings

    def _validate_executable_flags_against_tokens(
        self,
        executable_flags: Sequence[ExecutableFlag],
        taken_tokens: set[str],
    ) -> None:
        executable_tokens = executable_flag_tokens(executable_flags)
        for help_flag in self.context.help_flags:
            if help_flag in executable_tokens:
                raise ReservedFlagError(help_flag)

        for token in executable_tokens:
            if token in taken_tokens:
                raise ReservedFlagError(token)

    def _get_help_for_class(
        self,
        cls: Class,
        *,
        rules: list[HelpSubcommandSortRule],
    ) -> str:
        try:
            return self.context.help_layout.get_help_for_class(cls, rules=rules)
        except TypeError:
            return self.context.help_layout.get_help_for_class(cls)

    def _get_help_for_multiple_commands(
        self,
        commands: dict[str, Command],
        *,
        rules: list[HelpSubcommandSortRule] | None = None,
    ) -> str:
        if rules is None:
            return self.context.help_layout.get_help_for_multiple_commands(commands)

        try:
            return self.context.help_layout.get_help_for_multiple_commands(commands, rules=rules)
        except TypeError:
            return self.context.help_layout.get_help_for_multiple_commands(commands)

    def build_command_spec_for(
        self,
        obj: Class | Function | Method,
        *,
        canonical_name: str,
        description: str | None = None,
        aliases: tuple[str, ...] = (),
        executable_flags: list[ExecutableFlag] | None = None,
        parent_settings: CommandBuildSettings | None = None,
        include_inherited_methods: bool | None = None,
        include_protected_methods: bool | None = None,
        include_private_methods: bool | None = None,
        include_staticmethods: bool | None = None,
        include_classmethods: bool | None = None,
        method_skips: Sequence[str] | None = None,
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
            executable_flags (list[ExecutableFlag] | None): Zero-argument executable flags.
            parent_settings (CommandBuildSettings | None): Parent effective settings.
            include_inherited_methods (bool | None): Per-command inherited-method override.
            include_protected_methods (bool | None): Per-command protected-method override.
            include_private_methods (bool | None): Per-command private-method override.
            include_staticmethods (bool | None): Per-command staticmethod override.
            include_classmethods (bool | None): Per-command classmethod override.
            method_skips (Sequence[str] | None): Per-command method skip override.
            expand_model_params (bool | None): Per-command model expansion override.
            model_expansion_max_depth (int | None): Per-command depth override.
            abbreviation_scope (str | None): Per-command abbreviation scope override.
            help_option_sort (list[HelpOptionSortRule] | None): Per-command option rules.
            help_subcommand_sort (list[HelpSubcommandSortRule] | None): Per-command
                subcommand rules.
            help_group (str | None): Optional help-only command group heading.
        """
        return self.command_constructor.build_command_spec_for(
            obj,
            canonical_name=canonical_name,
            description=description,
            aliases=aliases,
            executable_flags=executable_flags,
            parent_settings=parent_settings,
            include_inherited_methods=include_inherited_methods,
            include_protected_methods=include_protected_methods,
            include_private_methods=include_private_methods,
            include_staticmethods=include_staticmethods,
            include_classmethods=include_classmethods,
            method_skips=method_skips,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=model_expansion_max_depth,
            abbreviation_scope=abbreviation_scope,
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
            help_group=help_group,
        )

    def _function_spec(
        self,
        function: Function | Method,
        *,
        canonical_name: str | None = None,
        description: str | None = None,
        aliases: tuple[str, ...] = (),
        cli_name_override: str | None = None,
        pipe_config: PipeTargets | None = None,
        executable_flags: list[ExecutableFlag] | None = None,
        settings: CommandBuildSettings | None = None,
        include_inherited_methods: bool | None = None,
        include_protected_methods: bool | None = None,
        include_private_methods: bool | None = None,
        include_staticmethods: bool | None = None,
        include_classmethods: bool | None = None,
        method_skips: Sequence[str] | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: str | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
    ) -> Command:
        resolved_settings = settings or self._base_build_settings()
        taken_flags = [*self.context.reserved_flags]
        flag_state = FlagAllocationState()
        effective_pipe_config = pipe_config
        if pipe_config is None and canonical_name is not None:
            effective_pipe_config = self.context.resolve_pipe_targets_by_names(
                canonical_name=canonical_name,
                obj_name=function.name,
                aliases=aliases,
                subcommand=None,
                include_default=True,
            )

        pipe_param_names = (
            effective_pipe_config.targeted_parameters() if effective_pipe_config else set()
        )

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
        resolved_executable_flags = list(executable_flags or [])
        self._validate_executable_flags_against_tokens(
            resolved_executable_flags,
            self._argument_option_strings(parameters),
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
            help_layout=self.context.help_layout,
            executable_flags=resolved_executable_flags,
        )
        self._attach_command_build_settings(
            command,
            settings=resolved_settings,
            include_inherited_methods=include_inherited_methods,
            include_protected_methods=include_protected_methods,
            include_private_methods=include_private_methods,
            include_staticmethods=include_staticmethods,
            include_classmethods=include_classmethods,
            method_skips=method_skips,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=model_expansion_max_depth,
            abbreviation_scope=abbreviation_scope,
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
            help_group=help_group,
        )

        return command

    @staticmethod
    def _pipe_config_for_params(
        pipe_config: PipeTargets | None,
        params: Sequence[Parameter],
    ) -> PipeTargets | None:
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

    def _method_command(
        self,
        method: Method,
        *,
        canonical_name: str | None = None,
        description: str | None = None,
        aliases: tuple[str, ...] = (),
        executable_flags: list[ExecutableFlag] | None = None,
        settings: CommandBuildSettings | None = None,
        include_inherited_methods: bool | None = None,
        include_protected_methods: bool | None = None,
        include_private_methods: bool | None = None,
        include_staticmethods: bool | None = None,
        include_classmethods: bool | None = None,
        method_skips: Sequence[str] | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: str | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
    ) -> Command:
        resolved_settings = settings or self._base_build_settings()
        taken_flags = [*self.context.reserved_flags]
        init_flag_state = FlagAllocationState()
        method_flag_state = FlagAllocationState()

        initializer: list[Argument] = []
        is_initialized = hasattr(method.func, "__self__")
        init_pipe_config: PipeTargets | None = None
        if canonical_name is not None:
            init_pipe_config = self.context.resolve_pipe_targets_by_names(
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
            class_arg_docs = ModelArgumentMapper._parse_docstring_args(method.cls.__doc__)
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
                    description_override=class_arg_docs.get(param.name),
                )
            ]
        else:
            self._prepare_layout_for_params(method.params)

        method_pipe_config = None
        if canonical_name is not None:
            method_pipe_config = self.context.resolve_pipe_targets_by_names(
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
        resolved_executable_flags = list(executable_flags or [])
        self._validate_executable_flags_against_tokens(
            resolved_executable_flags,
            self._argument_option_strings([*initializer, *parameters]),
        )

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
            help_layout=self.context.help_layout,
            executable_flags=resolved_executable_flags,
        )
        self._attach_command_build_settings(
            command,
            settings=resolved_settings,
            include_inherited_methods=include_inherited_methods,
            include_protected_methods=include_protected_methods,
            include_private_methods=include_private_methods,
            include_staticmethods=include_staticmethods,
            include_classmethods=include_classmethods,
            method_skips=method_skips,
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
        executable_flags: list[ExecutableFlag] | None = None,
        settings: CommandBuildSettings | None = None,
        include_inherited_methods: bool | None = None,
        include_protected_methods: bool | None = None,
        include_private_methods: bool | None = None,
        include_staticmethods: bool | None = None,
        include_classmethods: bool | None = None,
        method_skips: Sequence[str] | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: str | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
    ) -> Command:
        resolved_settings = settings or self._base_build_settings()
        taken_flags = [*self.context.reserved_flags]
        command_key = self.context.command_key
        if command_key:
            taken_flags.append(command_key)

        init_flag_state = FlagAllocationState()

        initializer: list[Argument] = []
        class_pipe_config = None
        init_pipe_config = None
        if canonical_name is not None:
            class_pipe_config = self.context.resolve_pipe_targets_by_names(
                canonical_name=canonical_name,
                obj_name=cls.name,
                aliases=aliases,
                subcommand=None,
                include_default=False,
            )
            init_pipe_config = (
                self.context.resolve_pipe_targets_by_names(
                    canonical_name=canonical_name,
                    obj_name=cls.name,
                    aliases=aliases,
                    subcommand="__init__",
                    include_default=False,
                )
                or class_pipe_config
            )

        if cls.has_init and not cls.is_initialized:
            init_params = cls.get_method("__init__").params
            class_arg_docs = ModelArgumentMapper._parse_docstring_args(cls.cls.__doc__)
            self._prepare_layout_for_params(init_params)
            init_pipe_names = init_pipe_config.targeted_parameters() if init_pipe_config else set()
            initializer = [
                arg
                for param in init_params
                for arg in self._argument_from_parameter(
                    param,
                    taken_flags,
                    init_pipe_names,
                    settings=resolved_settings,
                    flag_allocation_state=init_flag_state,
                    description_override=class_arg_docs.get(param.name),
                )
            ]

        subcommands: dict[str, Command] = {}

        for method in cls.methods:
            if method.name in resolved_settings.method_skips:
                continue

            method_cli_name = self.context.flag_strategy.command_translator.translate(method.name)
            sub_pipe_config = None
            if canonical_name is not None:
                sub_pipe_config = (
                    self.context.resolve_pipe_targets_by_names(
                        canonical_name=canonical_name,
                        obj_name=cls.name,
                        aliases=aliases,
                        subcommand=method_cli_name,
                        include_default=False,
                    )
                    or self.context.resolve_pipe_targets_by_names(
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
        resolved_executable_flags = list(executable_flags or [])
        self._validate_executable_flags_against_tokens(
            resolved_executable_flags,
            self._argument_option_strings(initializer),
        )

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
            help_layout=self.context.help_layout,
            executable_flags=resolved_executable_flags,
            command_type="class",
            is_leaf=False,
            metadata={"_interfacy_derived_epilog": True},
        )
        self._attach_command_build_settings(
            command,
            settings=resolved_settings,
            include_inherited_methods=include_inherited_methods,
            include_protected_methods=include_protected_methods,
            include_private_methods=include_private_methods,
            include_staticmethods=include_staticmethods,
            include_classmethods=include_classmethods,
            method_skips=method_skips,
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
        settings: CommandBuildSettings | None = None,
        flag_allocation_state: FlagAllocationState | None = None,
        description_override: str | None = None,
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

        translated_name = self.context.flag_strategy.argument_translator.translate(param.name)
        if translated_name in taken_flags:
            raise ReservedFlagError(translated_name)

        flags = get_arg_flags_for_parameter(
            self.context.flag_strategy,
            translated_name,
            param,
            taken_flags,
            self.context.abbreviation_gen,
            allocation_state=flag_allocation_state,
        )
        taken_flags.append(translated_name)

        spec = ParamSpec(
            name=param.name,
            type=annotation,
            is_typed=param.is_typed,
            has_default=param.has_default,
            default=param.default if param.has_default else None,
            is_required=param.is_required,
            is_optional=param.is_optional,
            kind=param.kind,
            description=param.description or description_override,
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
        return getattr(self.context.flag_strategy, "nested_separator", ".")

    def _should_expand_model(
        self,
        param_type: Any,
        *,
        settings: CommandBuildSettings,
    ) -> bool:
        registered_parsers = getattr(self.context.type_parser, "parsers", {})
        if param_type in registered_parsers and self.model_argument_mapper.is_plain_class_model(
            param_type
        ):
            return False

        return self.model_argument_mapper.should_expand_model(
            param_type,
            expand_model_params=settings.expand_model_params,
        )

    def _argument_value_plan(
        self,
        annotation: Any,
        *,
        settings: CommandBuildSettings,
        allow_repeated: bool = True,
    ) -> ArgumentValue:
        annotation = resolve_type_alias(annotation)
        if annotation is None:
            return UntypedValue()
        if annotation is bool:
            return FlagValue()

        optional_union_list = extract_optional_union_list(annotation)
        union_list = extract_union_list(annotation)
        if allow_repeated and (
            optional_union_list or union_list or is_list_or_list_alias(annotation)
        ):
            if optional_union_list:
                _list_annotation, element_type = optional_union_list
            elif union_list:
                _list_annotation, element_type = union_list
            else:
                element_args = type_args(annotation)
                element_type = element_args[0] if element_args else None
            item_plan = (
                self._argument_value_plan(element_type, settings=settings, allow_repeated=False)
                if element_type is not None
                else UntypedValue()
            )

            return RepeatedValue(item_plan)

        fixed_tuple_plan = self._fixed_tuple_value_plan(annotation, settings=settings)
        if fixed_tuple_plan is not None:
            return fixed_tuple_plan

        object_plan = self._object_value_plan(annotation, settings=settings)
        if object_plan is not None:
            return object_plan

        return ScalarValue(annotation)

    def _fixed_tuple_value_plan(
        self,
        annotation: Any,
        *,
        settings: CommandBuildSettings,
    ) -> FixedTupleValue | None:
        tuple_type = extract_optional_union_tuple(annotation) or annotation
        if not is_fixed_tuple(tuple_type):
            return None

        tuple_info = get_fixed_tuple_info(tuple_type)
        if tuple_info is None:
            return None

        _element_count, element_types = tuple_info
        item_plans = tuple(
            self._argument_value_plan(element_type, settings=settings)
            for element_type in element_types
        )
        if not all(self._value_plan_is_fixed(item) for item in item_plans):
            return None

        return FixedTupleValue(item_plans)

    def _object_value_plan(
        self,
        annotation: Any,
        *,
        settings: CommandBuildSettings,
    ) -> ObjectValue | None:
        model_type, _is_optional_model = self.model_argument_mapper.unwrap_optional(annotation)
        if not self._should_expand_model(model_type, settings=settings):
            return None

        fields: list[ObjectFieldValue] = []
        for field in self.model_argument_mapper.model_fields_for_expansion(model_type):
            if not field.required:
                continue

            field_plan = self._argument_value_plan(field.annotation, settings=settings)
            if not self._value_plan_is_fixed(field_plan):
                return None

            fields.append(ObjectFieldValue(field.name, field_plan))

        if not fields:
            return None

        return ObjectValue(model_type, tuple(fields))

    @staticmethod
    def _value_plan_is_fixed(value_plan: ArgumentValue) -> bool:
        consumption = value_plan.token_consumption(required=True)
        return consumption.is_fixed and consumption.group_size > 0

    def _expand_model_parameter(
        self,
        *,
        param: Parameter,
        model_type: type,
        is_optional_model: bool,
        taken_flags: list[str],
        settings: CommandBuildSettings,
    ) -> list[Argument]:
        return ModelExpansionBuilder(
            builder=self,
            param=param,
            taken_flags=taken_flags,
            settings=settings,
        ).build(model_type=model_type, is_optional_model=is_optional_model)

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
        settings: CommandBuildSettings,
    ) -> list[Argument]:
        del max_depth
        parameter = ExpansionParameter(
            name=root_name,
            default=model_default,
            has_default=model_default is not MODEL_DEFAULT_UNSET,
        )
        return ModelExpansionBuilder(
            builder=self,
            param=parameter,
            taken_flags=taken_flags,
            settings=settings,
        )._fields(
            model_type=model_type,
            root_name=root_name,
            path=path,
            depth=depth,
            parent_optional=parent_optional,
            parent_has_default=parent_has_default,
            original_model_type=original_model_type,
            model_default=model_default,
        )

    def _expanded_option_flags(
        self,
        *,
        display_name: str,
        annotation: Any,
        field_default: Any,
        taken_flags: list[str],
        settings: CommandBuildSettings,
    ) -> tuple[str, ...]:
        dummy_param = ExpansionParameter(
            name=display_name,
            default=None,
            has_default=False,
        )
        return ModelExpansionBuilder(
            builder=self,
            param=dummy_param,
            taken_flags=taken_flags,
            settings=settings,
        )._option_flags(
            display_name=display_name,
            annotation=annotation,
            field_default=field_default,
        )

    def _argument_from_spec(
        self,
        *,
        spec: ParamSpec,
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
        model_default: Any = MODEL_DEFAULT_UNSET,
        settings: CommandBuildSettings,
    ) -> Argument:
        resolved_help_text = help_text if help_text is not None else spec.description
        state = self._initial_argument_state(spec)

        if spec.kind == InspectParameter.VAR_POSITIONAL:
            self._configure_var_positional_state(spec, state, settings=settings)
        elif spec.is_typed:
            self._configure_typed_argument_state(
                spec=spec,
                flags=flags,
                translated_name=translated_name,
                allow_optional_union_list=allow_optional_union_list,
                state=state,
                settings=settings,
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
            metavar=(
                None
                if is_expanded_from is not None and spec.is_typed and spec.type is not bool
                else self._metavar_for_spec(spec)
            ),
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
            value_plan=state.value_plan,
        )

    def _initial_argument_state(self, spec: ParamSpec) -> ArgumentBuildState:
        choices: tuple[Any, ...] | None = None
        if spec.is_typed and (raw_choices := get_param_choices(spec, for_display=False)):
            choices = tuple(raw_choices)

        return ArgumentBuildState(
            parser_func=None,
            value_shape=ValueShape.SINGLE,
            nargs=None,
            default_value=spec.default if spec.has_default else None,
            parsed_type=spec.type if spec.is_typed else None,
            choices=choices,
            boolean_behavior=None,
            value_plan=None,
        )

    def _configure_var_positional_state(
        self,
        spec: ParamSpec,
        state: ArgumentBuildState,
        *,
        settings: CommandBuildSettings,
    ) -> None:
        state.value_shape = ValueShape.LIST
        state.nargs = "*"
        state.default_value = ()
        state.value_plan = RepeatedValue(
            self._argument_value_plan(spec.type, settings=settings)
            if spec.is_typed
            else UntypedValue()
        )
        if spec.is_typed:
            state.parsed_type = spec.type
            if spec.type is not str and not plan_requires_post_conversion(
                state.value_plan,
                required=spec.is_required,
            ):
                state.parser_func = self.context.type_parser.get_parse_func(spec.type)

    def _configure_typed_argument_state(
        self,
        *,
        spec: ParamSpec,
        flags: tuple[str, ...],
        translated_name: str,
        allow_optional_union_list: bool,
        state: ArgumentBuildState,
        settings: CommandBuildSettings,
    ) -> None:
        if self._configure_list_state(spec, allow_optional_union_list, state, settings=settings):
            return

        if self._configure_fixed_tuple_state(spec, state, settings=settings):
            return

        if self._configure_bool_state(spec, flags, translated_name, state):
            return

        self._configure_scalar_parser_state(spec, state)

    def _configure_list_state(
        self,
        spec: ParamSpec,
        allow_optional_union_list: bool,
        state: ArgumentBuildState,
        *,
        settings: CommandBuildSettings,
    ) -> bool:
        optional_union_list = extract_optional_union_list(spec.type)
        union_list = extract_union_list(spec.type)
        list_annotation: Any | None = None
        element_type: Any | None = None

        if optional_union_list:
            list_annotation, element_type = optional_union_list
            state.is_optional_union_list = True
        elif union_list:
            list_annotation, element_type = union_list
        elif is_list_or_list_alias(spec.type):
            list_annotation = spec.type
            element_args = type_args(spec.type)
            element_type = element_args[0] if element_args else None

        if list_annotation is None:
            return False

        state.value_shape = ValueShape.LIST
        item_plan = (
            self._argument_value_plan(element_type, settings=settings, allow_repeated=False)
            if element_type is not None
            else UntypedValue()
        )
        state.value_plan = RepeatedValue(item_plan)
        list_is_effectively_optional = state.is_optional_union_list and allow_optional_union_list
        state.nargs = "+" if spec.is_required and not list_is_effectively_optional else "*"

        if element_type is not None:
            state.parsed_type = element_type
            if state.choices is None:
                raw_choices = get_annotation_choices(element_type, for_display=False)
                if raw_choices:
                    state.choices = tuple(raw_choices)
            if element_type is not str and not plan_requires_post_conversion(
                state.value_plan,
                required=spec.is_required,
            ):
                state.parser_func = self.context.type_parser.get_parse_func(element_type)
        else:
            state.parsed_type = None
            state.parser_func = None

        if state.is_optional_union_list and not spec.has_default and allow_optional_union_list:
            state.default_value = []

        return True

    def _configure_fixed_tuple_state(
        self,
        spec: ParamSpec,
        state: ArgumentBuildState,
        *,
        settings: CommandBuildSettings,
    ) -> bool:
        tuple_type = extract_optional_union_tuple(spec.type) or spec.type
        if not is_fixed_tuple(tuple_type):
            return False

        tuple_info = get_fixed_tuple_info(tuple_type)
        if tuple_info is None:
            return True

        element_count, element_types = tuple_info
        state.value_shape = ValueShape.TUPLE
        state.nargs = element_count
        tuple_plan = self._fixed_tuple_value_plan(spec.type, settings=settings)
        if tuple_plan is not None:
            state.value_plan = tuple_plan
            state.parser_func = None
            state.tuple_element_parsers = None
            state.parsed_type = spec.type
            state.nargs = tuple_plan.token_consumption(required=True).group_size

            return True
        first_type = element_types[0]
        all_same_type = all(t == first_type for t in element_types)

        if all_same_type:
            state.parsed_type = first_type
            state.parser_func = self.context.type_parser.get_parse_func(first_type)
        else:
            state.tuple_element_parsers = tuple(
                self.context.type_parser.get_parse_func(t) for t in element_types
            )
            state.parsed_type = str
            state.parser_func = None

        return True

    def _configure_bool_state(
        self,
        spec: ParamSpec,
        flags: tuple[str, ...],
        translated_name: str,
        state: ArgumentBuildState,
    ) -> bool:
        if spec.type is not bool:
            return False

        state.value_shape = ValueShape.FLAG
        state.value_plan = FlagValue()
        supports_negative = any(flag.startswith("--") for flag in flags)
        negative_form = None
        mode = BooleanMode.DUAL
        state.default_value = spec.default if spec.has_default else False
        long_flags = [flag for flag in flags if flag.startswith("--")]
        primary_long_name = long_flags[0][2:] if long_flags else translated_name
        if (
            self.context.negative_bool_name_mode == "flag_only"
            and state.default_value is False
            and any(
                primary_long_name.startswith(prefix)
                for prefix in self.context.negative_bool_name_prefixes
            )
        ):
            supports_negative = False
            mode = BooleanMode.FLAG_ONLY

        if supports_negative:
            prefix = self.context.bool_negative_prefix
            if prefix is not None:
                negative_form = f"--{inverted_bool_flag_name(primary_long_name, prefix=prefix)}"

        state.boolean_behavior = BooleanBehavior(
            supports_negative=supports_negative,
            negative_form=negative_form,
            default=state.default_value,
            mode=mode,
        )

        return True

    def _configure_scalar_parser_state(
        self,
        spec: ParamSpec,
        state: ArgumentBuildState,
    ) -> None:
        state.value_plan = ScalarValue(spec.type)
        if spec.type is not str:
            state.parser_func = self.context.type_parser.get_parse_func(spec.type)

    def _metavar_for_spec(self, spec: ParamSpec) -> str | None:
        if self.context.help_layout.clear_metavar and not spec.is_required:
            return "\b"

        return None

    def _argument_kind_from_flags(self, flags: tuple[str, ...]) -> ArgumentKind:
        if any(flag.startswith("-") for flag in flags):
            return ArgumentKind.OPTION

        return ArgumentKind.POSITIONAL

    def _required_for_spec(
        self,
        *,
        spec: ParamSpec,
        allow_optional_union_list: bool,
        accepts_stdin: bool,
        kind: ArgumentKind,
        state: ArgumentBuildState,
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
        state: ArgumentBuildState,
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
                mode=state.boolean_behavior.mode,
            )

    def build_from_group(
        self,
        group: CommandGroup,
        parent_path: tuple[str, ...] = (),
        canonical_name: str | None = None,
        parent_settings: CommandBuildSettings | None = None,
        include_inherited_methods: bool | None = None,
        include_protected_methods: bool | None = None,
        include_private_methods: bool | None = None,
        include_staticmethods: bool | None = None,
        include_classmethods: bool | None = None,
        method_skips: Sequence[str] | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: str | None = None,
        executable_flags: list[ExecutableFlag] | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
    ) -> Command:
        """Build Command schema from a CommandGroup (manual construction)."""
        settings = self._merge_build_settings(
            parent_settings,
            include_inherited_methods=include_inherited_methods,
            include_protected_methods=include_protected_methods,
            include_private_methods=include_private_methods,
            include_staticmethods=include_staticmethods,
            include_classmethods=include_classmethods,
            method_skips=method_skips,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=model_expansion_max_depth,
            abbreviation_scope=abbreviation_scope,
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
        )
        cli_name = canonical_name or self.context.flag_strategy.command_translator.translate(
            group.name
        )
        current_path = (*parent_path, cli_name)

        initializer: list[Argument] = []
        group_args_source = self._get_group_args_source(group)
        if group_args_source is not None:
            initializer = self._build_args_from_source(group_args_source, settings=settings)
        resolved_executable_flags = list(executable_flags or [])
        self._validate_executable_flags_against_tokens(
            resolved_executable_flags,
            self._argument_option_strings(initializer),
        )

        subcommands: dict[str, Command] = {}
        translated_child_names: set[str] = set()

        def register_translated_child(name: str, aliases: tuple[str, ...] = ()) -> None:
            cli_name = self.context.flag_strategy.command_translator.translate(name)
            translated_aliases = tuple(
                self.context.flag_strategy.command_translator.translate(alias) for alias in aliases
            )
            candidates = (cli_name, *translated_aliases)
            if len(set(candidates)) != len(candidates):
                raise DuplicateCommandError(cli_name)

            for candidate in candidates:
                if candidate in translated_child_names:
                    raise DuplicateCommandError(candidate)

            translated_child_names.update(candidates)

        for name, subgroup_entry in group.subgroup_entries.items():
            sub_cli_name = self.context.flag_strategy.command_translator.translate(name)
            register_translated_child(name)
            subcommands[sub_cli_name] = self.build_from_group(
                subgroup_entry.group,
                current_path,
                parent_settings=settings,
                executable_flags=subgroup_entry.executable_flags,
                help_group=subgroup_entry.help_group,
            )

        for name, entry in group.commands.items():
            sub_cli_name = self.context.flag_strategy.command_translator.translate(name)
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
            executable_flags=resolved_executable_flags,
            raw_epilog=raw_epilog,
            help_layout=self.context.help_layout,
            command_type="group",
            is_leaf=False,
            parent_path=parent_path,
            metadata={"_interfacy_derived_epilog": bool(raw_epilog)},
        )
        self._attach_command_build_settings(
            command,
            settings=settings,
            include_inherited_methods=include_inherited_methods,
            include_protected_methods=include_protected_methods,
            include_private_methods=include_private_methods,
            include_staticmethods=include_staticmethods,
            include_classmethods=include_classmethods,
            method_skips=method_skips,
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
        settings: CommandBuildSettings,
    ) -> list[Argument]:
        """Build argument list from a class __init__ or callable signature."""
        obj = inspect(source, init=True)
        resolve_objinspect_annotations(obj)

        taken_flags = [*self.context.reserved_flags]
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
        parent_settings: CommandBuildSettings,
    ) -> Command:
        """Build Command from a CommandEntry (function/class/instance)."""
        settings = self._merge_build_settings(
            parent_settings,
            include_inherited_methods=entry.include_inherited_methods,
            include_protected_methods=entry.include_protected_methods,
            include_private_methods=entry.include_private_methods,
            include_staticmethods=entry.include_staticmethods,
            include_classmethods=entry.include_classmethods,
            method_skips=entry.method_skips,
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
                include_protected_methods=entry.include_protected_methods,
                include_private_methods=entry.include_private_methods,
                include_staticmethods=entry.include_staticmethods,
                include_classmethods=entry.include_classmethods,
                method_skips=entry.method_skips,
                expand_model_params=entry.expand_model_params,
                model_expansion_max_depth=entry.model_expansion_max_depth,
                abbreviation_scope=entry.abbreviation_scope,
                help_option_sort=entry.help_option_sort,
                help_subcommand_sort=entry.help_subcommand_sort,
                executable_flags=entry.executable_flags,
                help_group=entry.help_group,
            )

        if isinstance(entry.obj, type):
            return self._build_from_class_recursive(
                entry,
                parent_path,
                settings=settings,
                include_inherited_methods=entry.include_inherited_methods,
                include_protected_methods=entry.include_protected_methods,
                include_private_methods=entry.include_private_methods,
                include_staticmethods=entry.include_staticmethods,
                include_classmethods=entry.include_classmethods,
                method_skips=entry.method_skips,
                expand_model_params=entry.expand_model_params,
                model_expansion_max_depth=entry.model_expansion_max_depth,
                abbreviation_scope=entry.abbreviation_scope,
                help_option_sort=entry.help_option_sort,
                help_subcommand_sort=entry.help_subcommand_sort,
                executable_flags=entry.executable_flags,
                help_group=entry.help_group,
            )

        obj = inspect(entry.obj)
        resolve_objinspect_annotations(obj)

        if isinstance(obj, (Function, Method)):
            cli_name = self.context.flag_strategy.command_translator.translate(entry.name)
            return self._function_spec(
                obj,
                canonical_name=cli_name,
                description=entry.description,
                aliases=entry.aliases,
                pipe_config=entry.pipe_targets,
                settings=settings,
                include_inherited_methods=entry.include_inherited_methods,
                include_protected_methods=entry.include_protected_methods,
                include_private_methods=entry.include_private_methods,
                include_staticmethods=entry.include_staticmethods,
                include_classmethods=entry.include_classmethods,
                method_skips=entry.method_skips,
                expand_model_params=entry.expand_model_params,
                model_expansion_max_depth=entry.model_expansion_max_depth,
                abbreviation_scope=entry.abbreviation_scope,
                executable_flags=entry.executable_flags,
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
        settings: CommandBuildSettings,
        include_inherited_methods: bool | None = None,
        include_protected_methods: bool | None = None,
        include_private_methods: bool | None = None,
        include_staticmethods: bool | None = None,
        include_classmethods: bool | None = None,
        method_skips: Sequence[str] | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: str | None = None,
        executable_flags: list[ExecutableFlag] | None = None,
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
            static_methods=settings.include_staticmethods,
            classmethod=settings.include_classmethods,
            protected=settings.include_protected_methods,
            private=settings.include_private_methods,
        )
        assert isinstance(cls, Class)
        resolve_objinspect_annotations(cls)

        subcommands: dict[str, Command] = {}
        for method in cls.methods:
            if method.name in settings.method_skips:
                continue
            method_cli_name = self.context.flag_strategy.command_translator.translate(method.name)
            subcommands[method_cli_name] = self._function_spec(
                method,
                canonical_name=None,
                description=None,
                aliases=(),
                cli_name_override=method_cli_name,
                pipe_config=entry.pipe_targets,
                settings=settings,
            )

        cli_name = self.context.flag_strategy.command_translator.translate(entry.name)
        raw_description = entry.description or (cls.description if cls.has_docstring else None)
        resolved_executable_flags = list(executable_flags or [])
        self._validate_executable_flags_against_tokens(
            resolved_executable_flags,
            set(),
        )

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
            executable_flags=resolved_executable_flags,
            raw_epilog=raw_epilog,
            pipe_targets=entry.pipe_targets,
            help_layout=self.context.help_layout,
            command_type="instance",
            is_leaf=False,
            is_instance=True,
            parent_path=parent_path,
            stored_instance=instance,
            metadata={"_interfacy_derived_epilog": bool(raw_epilog)},
        )
        self._attach_command_build_settings(
            command,
            settings=settings,
            include_inherited_methods=include_inherited_methods,
            include_protected_methods=include_protected_methods,
            include_private_methods=include_private_methods,
            include_staticmethods=include_staticmethods,
            include_classmethods=include_classmethods,
            method_skips=method_skips,
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
        settings: CommandBuildSettings,
        include_inherited_methods: bool | None = None,
        include_protected_methods: bool | None = None,
        include_private_methods: bool | None = None,
        include_staticmethods: bool | None = None,
        include_classmethods: bool | None = None,
        method_skips: Sequence[str] | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: str | None = None,
        executable_flags: list[ExecutableFlag] | None = None,
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
            static_methods=settings.include_staticmethods,
            classmethod=settings.include_classmethods,
            protected=settings.include_protected_methods,
            private=settings.include_private_methods,
        )
        assert isinstance(cls, Class)
        resolve_objinspect_annotations(cls)
        cli_name = self.context.flag_strategy.command_translator.translate(entry.name)
        current_path = (*parent_path, cli_name)

        taken_flags = [*self.context.reserved_flags]
        command_key = self.context.command_key
        if command_key:
            taken_flags.append(command_key)

        init_flag_state = FlagAllocationState()

        initializer: list[Argument] = []
        init_params = (
            cls.get_method("__init__").params if cls.has_init and not cls.is_initialized else []
        )
        init_pipe_config = self._pipe_config_for_params(entry.pipe_targets, init_params)

        if init_params:
            init_pipe_names = init_pipe_config.targeted_parameters() if init_pipe_config else set()
            self._prepare_layout_for_params(init_params)
            initializer = [
                arg
                for param in init_params
                for arg in self._argument_from_parameter(
                    param,
                    taken_flags,
                    init_pipe_names,
                    settings=settings,
                    flag_allocation_state=init_flag_state,
                )
            ]

        subcommands: dict[str, Command] = {}

        for method in cls.methods:
            if method.name in settings.method_skips:
                continue

            method_cli_name = self.context.flag_strategy.command_translator.translate(method.name)
            method_pipe_config = self._pipe_config_for_params(entry.pipe_targets, method.params)
            subcommands[method_cli_name] = self._function_spec(
                method,
                canonical_name=None,
                description=None,
                aliases=(),
                cli_name_override=method_cli_name,
                pipe_config=method_pipe_config,
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
                    pipe_targets=None,
                    executable_flags=None,
                )
                nested_cli_name = self.context.flag_strategy.command_translator.translate(attr_name)
                subcommands[nested_cli_name] = self._build_from_class_recursive(
                    nested_entry,
                    current_path,
                    settings=settings,
                )

        raw_description = entry.description or (cls.description if cls.has_docstring else None)
        resolved_executable_flags = list(executable_flags or [])
        self._validate_executable_flags_against_tokens(
            resolved_executable_flags,
            self._argument_option_strings(initializer),
        )

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
            executable_flags=resolved_executable_flags,
            raw_epilog=raw_epilog,
            pipe_targets=init_pipe_config,
            help_layout=self.context.help_layout,
            command_type="class",
            is_leaf=False,
            parent_path=parent_path,
            metadata={"_interfacy_derived_epilog": bool(raw_epilog)},
        )
        self._attach_command_build_settings(
            command,
            settings=settings,
            include_inherited_methods=include_inherited_methods,
            include_protected_methods=include_protected_methods,
            include_private_methods=include_private_methods,
            include_staticmethods=include_staticmethods,
            include_classmethods=include_classmethods,
            method_skips=method_skips,
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

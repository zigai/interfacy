from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from inspect import Parameter as InspectParameter
from types import NoneType
from typing import TYPE_CHECKING, Any

from objinspect import Class, Function, Method, Parameter, inspect
from objinspect.typing import is_union_type, type_args

from interfacy.exceptions import (
    ConfigurationError,
    DuplicateCommandError,
    InvalidCommandError,
    ReservedFlagError,
)
from interfacy.executable_flag import ExecutableFlag, executable_flag_tokens
from interfacy.naming.flag_strategy import FlagAllocationState, get_arg_flags_for_parameter
from interfacy.naming.flags import inverted_bool_flag_name
from interfacy.parameters import Param, get_parameter_settings, merge_parameter_settings
from interfacy.pipe import PipeTargets
from interfacy.schema.arguments import (
    ArgumentBuildState,
    CommandOverrides,
    EffectiveCommandSettings,
    ParamSpec,
    resolve_command_settings,
)
from interfacy.schema.model_argument_mapper import ModelArgumentMapper
from interfacy.schema.model_expansion import ModelExpansionBuilder
from interfacy.schema.schema import (
    MODEL_DEFAULT_UNSET,
    Argument,
    ArgumentDefault,
    ArgumentKind,
    BooleanBehavior,
    BooleanMode,
    Command,
    ParserSchema,
    ValueCardinality,
    ValueShape,
)
from interfacy.schema.sorting import (
    DEFAULT_HELP_OPTION_SORT_RULES,
    DEFAULT_HELP_SUBCOMMAND_SORT_RULES,
    HelpOptionSortRule,
    HelpSubcommandSortRule,
    resolve_help_option_sort_rules,
    resolve_help_subcommand_sort_rules,
)
from interfacy.schema.typing import (
    extract_optional_union_list,
    extract_optional_union_tuple,
    extract_union_list,
    get_annotation_choices,
    get_fixed_tuple_info,
    get_param_choices,
    is_fixed_tuple,
    is_list_or_list_alias,
    resolve_objinspect_annotations,
    resolve_type_alias,
    simplified_type_name,
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

if TYPE_CHECKING:
    from interfacy.group import CommandEntry, CommandGroup


@dataclass
class SchemaBuildContext:
    """Backend-neutral source and policy snapshot for schema construction."""

    pipe_target_resolver: Callable[..., PipeTargets | None]
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
    help_flags: tuple[str, ...]


@dataclass
class ParserSchemaBuilder:
    """Build semantic parser schemas from an explicit neutral context."""

    context: SchemaBuildContext
    model_argument_mapper: ModelArgumentMapper = dataclass_field(
        default_factory=ModelArgumentMapper
    )

    def _resolve_help_option_sort_value(
        self,
        value: Any,
        *,
        value_name: str,
    ) -> list[HelpOptionSortRule]:
        rules = resolve_help_option_sort_rules(value, value_name=value_name)
        if rules:
            return list(rules)

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

        return list(DEFAULT_HELP_SUBCOMMAND_SORT_RULES)

    def _base_build_settings(self) -> EffectiveCommandSettings:
        help_option_sort = self._resolve_help_option_sort_value(
            self.context.help_option_sort,
            value_name="help_option_sort",
        )
        help_subcommand_sort = self._resolve_help_subcommand_sort_value(
            self.context.help_subcommand_sort,
            value_name="help_subcommand_sort",
        )
        return EffectiveCommandSettings(
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

    def _resolve_effective_command_settings(
        self,
        parent: EffectiveCommandSettings | None,
        overrides: CommandOverrides | None = None,
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
    ) -> EffectiveCommandSettings:
        base = parent or self._base_build_settings()
        if overrides is not None:
            return resolve_command_settings(base, overrides)

        resolved_overrides = CommandOverrides(
            include_inherited_methods=include_inherited_methods,
            include_protected_methods=include_protected_methods,
            include_private_methods=include_private_methods,
            include_staticmethods=include_staticmethods,
            include_classmethods=include_classmethods,
            method_skips=list(method_skips) if method_skips is not None else None,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=model_expansion_max_depth,
            abbreviation_scope=abbreviation_scope,
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
        )

        return resolve_command_settings(base, resolved_overrides)

    @staticmethod
    def _attach_command_build_settings(
        command: Command,
        *,
        settings: EffectiveCommandSettings,
        overrides: CommandOverrides | None = None,
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
        effective_overrides = overrides or CommandOverrides(
            include_inherited_methods=include_inherited_methods,
            include_protected_methods=include_protected_methods,
            include_private_methods=include_private_methods,
            include_staticmethods=include_staticmethods,
            include_classmethods=include_classmethods,
            method_skips=list(method_skips) if method_skips is not None else None,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=model_expansion_max_depth,
            abbreviation_scope=abbreviation_scope,
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
        )
        command.include_inherited_methods = effective_overrides.include_inherited_methods
        command.include_protected_methods = effective_overrides.include_protected_methods
        command.include_private_methods = effective_overrides.include_private_methods
        command.include_staticmethods = effective_overrides.include_staticmethods
        command.include_classmethods = effective_overrides.include_classmethods
        command.method_skips = (
            list(effective_overrides.method_skips)
            if effective_overrides.method_skips is not None
            else None
        )
        command.expand_model_params = effective_overrides.expand_model_params
        command.model_expansion_max_depth = effective_overrides.model_expansion_max_depth
        command.abbreviation_scope = effective_overrides.abbreviation_scope
        command.help_option_sort = (
            list(effective_overrides.help_option_sort)
            if effective_overrides.help_option_sort is not None
            else None
        )
        command.help_subcommand_sort = (
            list(effective_overrides.help_subcommand_sort)
            if effective_overrides.help_subcommand_sort is not None
            else None
        )
        command.help_group = help_group
        command.help_option_sort_effective = list(settings.help_option_sort)
        command.help_subcommand_sort_effective = list(settings.help_subcommand_sort)

    def build_unfinalized(self) -> ParserSchema:
        """Build raw semantic schema data without plugins or finalization."""
        commands: dict[str, Command] = {}
        for canonical_name, command in self.context.commands.items():
            if command.group_source is not None:
                rebuilt_group = self.build_from_group(
                    command.group_source,
                    canonical_name=command.canonical_name,
                    overrides=command.overrides,
                    help_group=command.help_group,
                    executable_flags=command.executable_flags,
                    parameter_settings=command.parameter_settings,
                )
                rebuilt_group.aliases = command.aliases
                rebuilt_group.raw_description = command.raw_description
                rebuilt_group.group_source = command.group_source
                commands[canonical_name] = rebuilt_group

                continue

            if command.command_type in ("group", "instance") or (
                not command.is_leaf and command.obj is None
            ):
                commands[canonical_name] = command
                continue
            if command.obj is None:
                raise InvalidCommandError(command.canonical_name)

            commands[canonical_name] = self.build_command_spec_for(
                command.obj,
                canonical_name=command.canonical_name,
                description=command.raw_description,
                aliases=command.aliases,
                executable_flags=command.executable_flags,
                parent_settings=None,
                overrides=command.overrides,
                help_group=command.help_group,
                parameter_settings=command.parameter_settings,
            )

        parser_executable_flags = list(getattr(self.context, "executable_flags", []))
        schema = ParserSchema(
            raw_description=self.context.description,
            raw_epilog=self.context.epilog,
            commands=commands,
            command_key=self.context.command_key,
            allow_args_from_file=self.context.allow_args_from_file,
            pipe_targets=self.context.pipe_targets_default,
            metadata=dict(getattr(self.context, "metadata", {})),
            executable_flags=parser_executable_flags,
            help_option_sort_effective=list(
                getattr(self.context, "help_option_sort_effective", [])
            ),
            help_subcommand_sort_effective=list(
                getattr(self.context, "help_subcommand_sort_effective", [])
            ),
            help_flags=self.context.help_flags,
        )
        return schema

    def build(self) -> ParserSchema:
        """Build and finalize a schema when no transform phase is required."""
        return self.finalize(self.build_unfinalized())

    def finalize(self, schema: ParserSchema) -> ParserSchema:
        """Finalize and validate a transformed semantic schema."""
        from interfacy.schema.schema import finalize_schema

        finalize_schema(schema)
        self._finalize_schema(schema)
        parser_executable_flags = list(schema.executable_flags)
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

    def _finalize_schema(self, schema: ParserSchema) -> None:
        root_option_rules = list(
            schema.help_option_sort_effective
            or getattr(self.context, "help_option_sort_effective", DEFAULT_HELP_OPTION_SORT_RULES)
        )
        root_subcommand_rules = list(
            schema.help_subcommand_sort_effective
            or getattr(
                self.context, "help_subcommand_sort_effective", DEFAULT_HELP_SUBCOMMAND_SORT_RULES
            )
        )
        for command in schema.commands.values():
            self._finalize_command(
                command,
                parent_option_rules=root_option_rules,
                parent_subcommand_rules=root_subcommand_rules,
            )

    def _finalize_command(
        self,
        command: Command,
        *,
        parent_option_rules: list[HelpOptionSortRule],
        parent_subcommand_rules: list[HelpSubcommandSortRule],
    ) -> None:
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

        if not command.subcommands:
            return

        for subcommand in command.subcommands.values():
            self._finalize_command(
                subcommand,
                parent_option_rules=command.help_option_sort_effective,
                parent_subcommand_rules=command.help_subcommand_sort_effective,
            )

    @staticmethod
    def _argument_option_strings(arguments: Sequence[Argument]) -> set[str]:
        option_strings: set[str] = set()
        for argument in arguments:
            if argument.kind is not ArgumentKind.OPTION:
                continue

            option_strings.update(flag for flag in argument.flags if flag.startswith("-"))

        return option_strings

    @staticmethod
    def _positional_arguments(arguments: Sequence[Argument]) -> list[Argument]:
        return [argument for argument in arguments if argument.kind is ArgumentKind.POSITIONAL]

    def _validate_positional_order(
        self,
        arguments: Sequence[Argument],
        *,
        owner: str,
    ) -> None:
        optional_argument: Argument | None = None
        for argument in self._positional_arguments(arguments):
            if optional_argument is not None and (
                optional_argument.value_shape is ValueShape.LIST or argument.required
            ):
                raise ConfigurationError(
                    f"Optional positional parameter '{optional_argument.display_name}' in "
                    f"'{owner}' cannot appear before positional parameter "
                    f"'{argument.display_name}'"
                )

            if not argument.required:
                optional_argument = argument

    def _validate_optional_initializer_positionals(
        self,
        *,
        owner: str,
        initializer: Sequence[Argument],
        subcommands: dict[str, Command],
    ) -> None:
        if not subcommands:
            return

        for argument in self._positional_arguments(initializer):
            if argument.required or argument.pipe_required:
                continue

            raise ConfigurationError(
                f"Optional initializer positional parameter '{argument.display_name}' in "
                f"'{owner}' is not allowed because the command has subcommands"
            )

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

    def build_command_spec_for(
        self,
        obj: Class | Function | Method,
        *,
        canonical_name: str,
        description: str | None = None,
        aliases: tuple[str, ...] = (),
        executable_flags: list[ExecutableFlag] | None = None,
        parent_settings: EffectiveCommandSettings | None = None,
        overrides: CommandOverrides | None = None,
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
        parameter_settings: dict[str, Param] | None = None,
    ) -> Command:
        """
        Build a Command schema for a callable or class.

        Args:
            obj (Class | Function | Method): Inspected target to convert.
            canonical_name (str): Canonical command name.
            description (str | None): Optional description override.
            aliases (tuple[str, ...]): Alternate command names.
            executable_flags (list[ExecutableFlag] | None): Zero-argument executable flags.
            parent_settings (EffectiveCommandSettings | None): Parent effective settings.
            overrides (CommandOverrides | None): Optional command settings override.
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
            parameter_settings (dict[str, Param] | None): Per-parameter settings.
        """
        effective_overrides = overrides or CommandOverrides(
            include_inherited_methods=include_inherited_methods,
            include_protected_methods=include_protected_methods,
            include_private_methods=include_private_methods,
            include_staticmethods=include_staticmethods,
            include_classmethods=include_classmethods,
            method_skips=list(method_skips) if method_skips is not None else None,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=model_expansion_max_depth,
            abbreviation_scope=abbreviation_scope,
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
        )
        settings = self._resolve_effective_command_settings(
            parent_settings,
            overrides=effective_overrides,
        )
        resolve_objinspect_annotations(obj)

        if isinstance(obj, Function):
            return self._function_spec(
                function=obj,
                canonical_name=canonical_name,
                description=description,
                aliases=aliases,
                executable_flags=executable_flags,
                settings=settings,
                overrides=effective_overrides,
                help_group=help_group,
                parameter_settings=parameter_settings,
            )
        if isinstance(obj, Method):
            return self._method_command(
                method=obj,
                canonical_name=canonical_name,
                description=description,
                aliases=aliases,
                executable_flags=executable_flags,
                settings=settings,
                overrides=effective_overrides,
                help_group=help_group,
                parameter_settings=parameter_settings,
            )
        if isinstance(obj, Class):
            return self._class_command(
                cls=obj,
                canonical_name=canonical_name,
                description=description,
                aliases=aliases,
                executable_flags=executable_flags,
                settings=settings,
                overrides=effective_overrides,
                help_group=help_group,
                parameter_settings=parameter_settings,
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
        executable_flags: list[ExecutableFlag] | None = None,
        settings: EffectiveCommandSettings | None = None,
        overrides: CommandOverrides | None = None,
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
        parameter_settings: dict[str, Param] | None = None,
    ) -> Command:
        resolved_settings = settings or self._base_build_settings()
        taken_flags = [*self.context.reserved_flags]
        flag_state = FlagAllocationState()
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
            self._callable_parameter_settings(function),
            parameter_settings,
        )

        parameters = [
            arg
            for param in function.params
            for arg in self._argument_from_parameter(
                param,
                taken_flags,
                pipe_param_names,
                settings=resolved_settings,
                flag_allocation_state=flag_state,
                parameter_setting=self._settings_for_param(effective_parameter_settings, param),
            )
        ]
        self._validate_positional_order(parameters, owner=canonical_name or function.name)
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
            executable_flags=resolved_executable_flags,
            parameter_settings=dict(effective_parameter_settings),
        )
        self._attach_command_build_settings(
            command,
            settings=resolved_settings,
            overrides=overrides,
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
    def _callable_parameter_settings(function: Function | Method) -> dict[str, Param]:
        return get_parameter_settings(function.func)

    @staticmethod
    def _class_parameter_settings(class_info: Class) -> dict[str, Param]:
        class_target = class_info.cls if isinstance(class_info.cls, type) else type(class_info.cls)
        class_settings = get_parameter_settings(class_target)
        init_settings = (
            get_parameter_settings(class_info.init_method.func)
            if class_info.init_method is not None
            else {}
        )

        return merge_parameter_settings(class_settings, init_settings)

    @staticmethod
    def _settings_for_param(settings: dict[str, Param], param: Parameter) -> Param | None:
        return settings.get(param.name)

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
        settings: EffectiveCommandSettings | None = None,
        overrides: CommandOverrides | None = None,
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
        parameter_settings: dict[str, Param] | None = None,
    ) -> Command:
        resolved_settings = settings or self._base_build_settings()
        taken_flags = [*self.context.reserved_flags]
        init_flag_state = FlagAllocationState()
        method_flag_state = FlagAllocationState()

        initializer: list[Argument] = []
        is_initialized = hasattr(method.func, "__self__")
        init_pipe_config: PipeTargets | None = None
        if canonical_name is not None:
            init_pipe_config = self.context.pipe_target_resolver(
                canonical_name=canonical_name,
                obj_name=method.name,
                aliases=aliases,
                subcommand="__init__",
                include_default=False,
            )

        init_pipe_names = init_pipe_config.targeted_parameters() if init_pipe_config else set()
        init_parameter_settings: dict[str, Param] = {}
        method_parameter_settings = merge_parameter_settings(
            self._callable_parameter_settings(method),
            parameter_settings,
        )

        if (init := Class(method.cls).init_method) and not is_initialized:
            init_parameter_settings = merge_parameter_settings(
                get_parameter_settings(method.cls),
                get_parameter_settings(init.func),
            )
            class_arg_docs = ModelArgumentMapper._parse_docstring_args(method.cls.__doc__)

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
                    parameter_setting=self._settings_for_param(init_parameter_settings, param),
                )
            ]
        method_pipe_config = None
        if canonical_name is not None:
            method_pipe_config = self.context.pipe_target_resolver(
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
                parameter_setting=self._settings_for_param(method_parameter_settings, param),
            )
        ]
        self._validate_positional_order(
            [*initializer, *parameters],
            owner=canonical_name or method.name,
        )

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
            executable_flags=resolved_executable_flags,
            parameter_settings=dict(method_parameter_settings),
        )
        self._attach_command_build_settings(
            command,
            settings=resolved_settings,
            overrides=overrides,
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
        settings: EffectiveCommandSettings | None = None,
        overrides: CommandOverrides | None = None,
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
        parameter_settings: dict[str, Param] | None = None,
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
            class_pipe_config = self.context.pipe_target_resolver(
                canonical_name=canonical_name,
                obj_name=cls.name,
                aliases=aliases,
                subcommand=None,
                include_default=False,
            )
            init_pipe_config = (
                self.context.pipe_target_resolver(
                    canonical_name=canonical_name,
                    obj_name=cls.name,
                    aliases=aliases,
                    subcommand="__init__",
                    include_default=False,
                )
                or class_pipe_config
            )

        effective_parameter_settings = merge_parameter_settings(
            self._class_parameter_settings(cls),
            parameter_settings,
        )

        if cls.has_init and not cls.is_initialized:
            init_params = cls.get_method("__init__").params
            class_arg_docs = ModelArgumentMapper._parse_docstring_args(cls.cls.__doc__)
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
                    parameter_setting=self._settings_for_param(effective_parameter_settings, param),
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
                    self.context.pipe_target_resolver(
                        canonical_name=canonical_name,
                        obj_name=cls.name,
                        aliases=aliases,
                        subcommand=method_cli_name,
                        include_default=False,
                    )
                    or self.context.pipe_target_resolver(
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
                parameter_settings=parameter_settings,
            )

        raw_description = description or (cls.description if cls.has_docstring else None)
        cli_name = self._resolve_cli_name(None, canonical_name, cls.name)
        self._validate_positional_order(initializer, owner=cli_name)
        self._validate_optional_initializer_positionals(
            owner=cli_name,
            initializer=initializer,
            subcommands=subcommands,
        )
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
            raw_epilog=None,
            pipe_targets=class_pipe_config,
            executable_flags=resolved_executable_flags,
            command_type="class",
            is_leaf=False,
            parameter_settings=dict(effective_parameter_settings),
        )
        self._attach_command_build_settings(
            command,
            settings=resolved_settings,
            overrides=overrides,
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
    def _flag_token_key(flag: str) -> str:
        return flag.lstrip("-")

    def _reserve_parameter_flags(self, flags: tuple[str, ...], taken_flags: list[str]) -> None:
        for flag in flags:
            key = self._flag_token_key(flag)
            if key in taken_flags:
                raise ReservedFlagError(key)

            taken_flags.append(key)

    def _default_long_flag(self, translated_name: str) -> str:
        return f"--{translated_name}"

    def _short_flag_from_setting(
        self,
        setting: Param,
        *,
        abbrev_name: str,
        taken_flags: list[str],
    ) -> str | None:
        if setting.short is False:
            return None
        if isinstance(setting.short, str):
            return setting.short
        if setting.short is True or setting.short is None:
            short = self.context.abbreviation_gen.generate(abbrev_name, list(taken_flags))
            return f"-{short.strip()}" if short else None

        return None

    def _flags_from_parameter_setting(
        self,
        *,
        translated_name: str,
        param: Parameter,
        setting: Param,
        taken_flags: list[str],
    ) -> tuple[str, ...]:
        if setting.flags is not None:
            flags = tuple(setting.flags)
            self._reserve_parameter_flags(flags, taken_flags)
            return flags

        long_flag = setting.long or f"--{translated_name}"
        flags: tuple[str, ...] = (long_flag,)
        abbrev_name = long_flag.lstrip("-")
        if param.is_typed and param.type is bool:
            default_value = param.default if param.has_default else False
            if default_value is True:
                abbrev_name = f"no-{abbrev_name}"

        short_flag = self._short_flag_from_setting(
            setting,
            abbrev_name=abbrev_name,
            taken_flags=taken_flags,
        )
        if short_flag and short_flag not in flags:
            flags = (short_flag, long_flag)

        self._reserve_parameter_flags(flags, taken_flags)

        return flags

    def _flags_for_parameter(
        self,
        *,
        translated_name: str,
        param: Parameter,
        taken_flags: list[str],
        flag_allocation_state: FlagAllocationState | None,
        parameter_setting: Param | None,
    ) -> tuple[str, ...]:
        if parameter_setting is not None and parameter_setting.kind == "positional":
            if translated_name in taken_flags:
                raise ReservedFlagError(translated_name)

            taken_flags.append(translated_name)

            return (translated_name,)

        if parameter_setting is not None and parameter_setting.kind == "option":
            return self._flags_from_parameter_setting(
                translated_name=translated_name,
                param=param,
                setting=parameter_setting,
                taken_flags=taken_flags,
            )

        if parameter_setting is not None and parameter_setting.has_flag_overrides:
            return self._flags_from_parameter_setting(
                translated_name=translated_name,
                param=param,
                setting=parameter_setting,
                taken_flags=taken_flags,
            )

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

        return flags

    def _argument_from_parameter(
        self,
        param: Parameter,
        taken_flags: list[str],
        pipe_param_names: set[str] | None = None,
        *,
        settings: EffectiveCommandSettings | None = None,
        flag_allocation_state: FlagAllocationState | None = None,
        description_override: str | None = None,
        parameter_setting: Param | None = None,
    ) -> list[Argument]:
        resolved_settings = settings or self._base_build_settings()
        annotation = resolve_type_alias(param.type)
        if isinstance(annotation, str):
            simple_name = simplified_type_name(annotation)
            base_name = simple_name.removesuffix("?")
            builtin_map = {"bool": bool, "int": int, "float": float, "str": str}
            if base_name in builtin_map:
                annotation = builtin_map[base_name]

        if is_union_type(annotation):
            annotation_args = type_args(annotation)
            if (
                len(annotation_args) == 2
                and NoneType in annotation_args
                and bool in annotation_args
            ):
                annotation = bool

        if parameter_setting is not None and annotation is not bool:
            if parameter_setting.boolean_mode is not BooleanMode.AUTO:
                raise ConfigurationError(
                    f"Param.boolean_mode can only configure boolean parameter '{param.name}'"
                )
            if parameter_setting.negative_flags is not None:
                raise ConfigurationError(
                    f"Param.negative_flags can only configure boolean parameter '{param.name}'"
                )

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
        flags = self._flags_for_parameter(
            translated_name=translated_name,
            param=param,
            taken_flags=taken_flags,
            flag_allocation_state=flag_allocation_state,
            parameter_setting=parameter_setting,
        )

        spec = ParamSpec(
            name=param.name,
            type=annotation,
            is_typed=param.is_typed,
            has_default=param.has_default,
            default=param.default if param.has_default else None,
            is_required=param.is_required,
            is_optional=param.is_optional,
            kind=param.kind,
            description=(
                parameter_setting.help
                if parameter_setting is not None and parameter_setting.help is not None
                else param.description or description_override
            ),
        )

        return [
            self._argument_from_spec(
                spec=spec,
                translated_name=translated_name,
                flags=flags,
                taken_flags=taken_flags,
                pipe_param_names=pipe_param_names,
                allow_optional_union_list=True,
                suppress_parse_default=False,
                settings=resolved_settings,
                parameter_setting=parameter_setting,
            )
        ]

    @property
    def _nested_separator(self) -> str:
        return getattr(self.context.flag_strategy, "nested_separator", ".")

    def _should_expand_model(
        self,
        param_type: Any,
        *,
        settings: EffectiveCommandSettings,
    ) -> bool:
        registered_parsers = getattr(self.context.type_parser, "parsers", {})
        try:
            has_parser = param_type in registered_parsers
        except TypeError:
            has_parser = False

        if has_parser and self.model_argument_mapper.is_plain_class_model(param_type):
            return False

        return self.model_argument_mapper.should_expand_model(
            param_type,
            expand_model_params=settings.expand_model_params,
        )

    def _argument_value_plan(
        self,
        annotation: Any,
        *,
        settings: EffectiveCommandSettings,
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
        settings: EffectiveCommandSettings,
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
        settings: EffectiveCommandSettings,
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
        settings: EffectiveCommandSettings,
    ) -> list[Argument]:
        return ModelExpansionBuilder(
            builder=self,
            param=param,
            taken_flags=taken_flags,
            settings=settings,
        ).build(model_type=model_type, is_optional_model=is_optional_model)

    def _argument_from_spec(
        self,
        *,
        spec: ParamSpec,
        translated_name: str,
        flags: tuple[str, ...],
        taken_flags: list[str],
        pipe_param_names: set[str] | None,
        allow_optional_union_list: bool,
        suppress_parse_default: bool,
        force_optional: bool = False,
        help_text: str | None = None,
        is_expanded_from: str | None = None,
        expansion_path: tuple[str, ...] = (),
        original_model_type: type | None = None,
        parent_is_optional: bool = False,
        model_default: Any = MODEL_DEFAULT_UNSET,
        settings: EffectiveCommandSettings,
        parameter_setting: Param | None = None,
    ) -> Argument:
        resolved_help_text = help_text if help_text is not None else spec.description
        state = self._initial_argument_state(spec)

        if spec.kind == InspectParameter.VAR_POSITIONAL:
            self._configure_var_positional_state(spec, state, settings=settings)
        elif spec.is_typed:
            self._configure_typed_argument_state(
                spec=spec,
                flags=flags,
                taken_flags=taken_flags,
                allow_optional_union_list=allow_optional_union_list,
                state=state,
                settings=settings,
                parameter_setting=parameter_setting,
            )

        if not spec.is_required and spec.is_typed and spec.type is not bool:
            state.argument_default = ArgumentDefault.present(spec.default)

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

        if state.value_shape is ValueShape.FLAG:
            cardinality = ValueCardinality(0, 0, 0)
        elif state.value_shape is ValueShape.LIST:
            item_size = state.cardinality.group_size
            min_count = (
                0 if spec.kind == InspectParameter.VAR_POSITIONAL or not required else item_size
            )
            cardinality = ValueCardinality(min_count, None, item_size)
        elif state.value_shape is ValueShape.TUPLE:
            cardinality = (
                state.value_plan.token_consumption(required=True)
                if state.value_plan is not None
                else state.cardinality
            )
        else:
            minimum = 0 if kind is ArgumentKind.POSITIONAL and not required else 1
            cardinality = ValueCardinality(minimum, 1, 1)
        argument_default = state.argument_default
        if suppress_parse_default and not required and argument_default.is_set:
            argument_default = ArgumentDefault.present(
                argument_default.value,
                suppress_parse_default=True,
                suppress_help_default=True,
            )

        return Argument(
            name=spec.name,
            display_name=translated_name,
            kind=kind,
            value_shape=state.value_shape,
            flags=flags,
            required=required,
            cardinality=cardinality,
            argument_default=argument_default,
            help=resolved_help_text,
            type=state.parsed_type,
            parser=state.parser_func,
            metavar=parameter_setting.metavar if parameter_setting is not None else None,
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
            cardinality=ValueCardinality(1 if spec.is_required else 0, 1, 1),
            argument_default=(
                ArgumentDefault.present(spec.default)
                if spec.has_default
                else ArgumentDefault.absent()
            ),
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
        settings: EffectiveCommandSettings,
    ) -> None:
        state.value_shape = ValueShape.LIST
        state.cardinality = ValueCardinality(0, None, 1)
        state.argument_default = ArgumentDefault.present(())
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
        taken_flags: list[str],
        allow_optional_union_list: bool,
        state: ArgumentBuildState,
        settings: EffectiveCommandSettings,
        parameter_setting: Param | None,
    ) -> None:
        if self._configure_list_state(spec, allow_optional_union_list, state, settings=settings):
            return

        if self._configure_fixed_tuple_state(spec, state, settings=settings):
            return

        if self._configure_bool_state(
            spec,
            flags,
            taken_flags,
            state,
            parameter_setting,
        ):
            return

        self._configure_scalar_parser_state(spec, state)

    def _configure_list_state(
        self,
        spec: ParamSpec,
        allow_optional_union_list: bool,
        state: ArgumentBuildState,
        *,
        settings: EffectiveCommandSettings,
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
        required = spec.is_required and not list_is_effectively_optional
        item_size = item_plan.token_consumption(required=True).group_size
        state.cardinality = ValueCardinality(item_size if required else 0, None, item_size)

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
            state.argument_default = ArgumentDefault.present([])

        return True

    def _configure_fixed_tuple_state(
        self,
        spec: ParamSpec,
        state: ArgumentBuildState,
        *,
        settings: EffectiveCommandSettings,
    ) -> bool:
        tuple_type = extract_optional_union_tuple(spec.type) or spec.type
        if not is_fixed_tuple(tuple_type):
            return False

        tuple_info = get_fixed_tuple_info(tuple_type)
        if tuple_info is None:
            return True

        element_count, element_types = tuple_info
        state.value_shape = ValueShape.TUPLE
        state.cardinality = ValueCardinality(element_count, element_count, element_count)
        tuple_plan = self._fixed_tuple_value_plan(spec.type, settings=settings)
        if tuple_plan is not None:
            state.value_plan = tuple_plan
            state.parser_func = None
            state.tuple_element_parsers = None
            state.parsed_type = spec.type
            state.cardinality = tuple_plan.token_consumption(required=spec.is_required)

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
        taken_flags: list[str],
        state: ArgumentBuildState,
        parameter_setting: Param | None,
    ) -> bool:
        if spec.type is not bool:
            return False

        if not any(flag.startswith("-") for flag in flags):
            raise ConfigurationError(f"Boolean parameter '{spec.name}' must be an option")

        state.value_shape = ValueShape.FLAG
        state.value_plan = FlagValue()
        state.cardinality = ValueCardinality(0, 0, 0)
        state.argument_default = ArgumentDefault.present(
            spec.default if spec.has_default else False
        )
        requested_mode = (
            parameter_setting.boolean_mode if parameter_setting is not None else BooleanMode.AUTO
        )
        if not isinstance(requested_mode, BooleanMode):
            raise ConfigurationError(f"Boolean parameter '{spec.name}' has an invalid boolean mode")

        configured_negative_flags = (
            tuple(parameter_setting.negative_flags)
            if parameter_setting is not None and parameter_setting.negative_flags is not None
            else None
        )
        mode = self._effective_boolean_mode(spec, requested_mode, configured_negative_flags)

        positive_flags = flags if mode in {BooleanMode.POSITIVE_ONLY, BooleanMode.DUAL} else ()
        negative_flags: tuple[str, ...] = ()

        if mode is BooleanMode.NEGATIVE_ONLY:
            for flag in flags:
                if flag.startswith("-") and not flag.startswith("--"):
                    short_name = self._flag_token_key(flag)
                    if short_name in taken_flags:
                        taken_flags.remove(short_name)

        if mode is BooleanMode.POSITIVE_ONLY and configured_negative_flags is not None:
            raise ConfigurationError(
                f"Boolean parameter '{spec.name}' cannot define negative flags in positive_only mode"
            )

        if mode in {BooleanMode.NEGATIVE_ONLY, BooleanMode.DUAL}:
            negative_flags = configured_negative_flags or self._generated_negative_flags(
                spec,
                flags,
            )
            self._reserve_parameter_flags(negative_flags, taken_flags)

        state.boolean_behavior = BooleanBehavior(
            positive_flags=positive_flags,
            negative_flags=negative_flags,
            default=state.argument_default.value,
            mode=mode,
        )

        return True

    def _effective_boolean_mode(
        self,
        spec: ParamSpec,
        requested_mode: BooleanMode,
        configured_negative_flags: tuple[str, ...] | None,
    ) -> BooleanMode:
        mode = self._resolve_boolean_mode(spec, requested_mode)

        if (
            self.context.bool_negative_prefix is None
            and configured_negative_flags is None
            and requested_mode is BooleanMode.AUTO
        ):
            return BooleanMode.POSITIVE_ONLY

        return mode

    @staticmethod
    def _resolve_boolean_mode(spec: ParamSpec, requested_mode: BooleanMode) -> BooleanMode:
        if requested_mode is BooleanMode.AUTO:
            if spec.has_default and spec.default is False:
                return BooleanMode.POSITIVE_ONLY
            if spec.has_default and spec.default is True:
                return BooleanMode.NEGATIVE_ONLY
            return BooleanMode.DUAL

        if requested_mode is BooleanMode.POSITIVE_ONLY and (
            not spec.has_default or spec.default is not False
        ):
            raise ConfigurationError(
                f"Boolean parameter '{spec.name}' uses positive_only mode but does not default "
                "to False"
            )
        if requested_mode is BooleanMode.NEGATIVE_ONLY and (
            not spec.has_default or spec.default is not True
        ):
            raise ConfigurationError(
                f"Boolean parameter '{spec.name}' uses negative_only mode but does not default "
                "to True"
            )

        return requested_mode

    def _generated_negative_flags(
        self,
        spec: ParamSpec,
        flags: tuple[str, ...],
    ) -> tuple[str, ...]:
        if self.context.bool_negative_prefix is None:
            return ()

        long_flags = [flag for flag in flags if flag.startswith("--")]
        if not long_flags:
            raise ConfigurationError(
                f"Boolean parameter '{spec.name}' requires Param.negative_flags because its "
                "positive flags do not include a long option"
            )

        primary_long_name = long_flags[0][2:]
        negative_name = inverted_bool_flag_name(
            primary_long_name,
            prefix=self.context.bool_negative_prefix,
        )
        return (f"--{negative_name}",)

    def _configure_scalar_parser_state(
        self,
        spec: ParamSpec,
        state: ArgumentBuildState,
    ) -> None:
        state.value_plan = ScalarValue(spec.type)
        if spec.type is not str:
            try:
                state.parser_func = self.context.type_parser.get_parse_func(spec.type)
            except TypeError:
                state.parser_func = None

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
            return False

        if allow_optional_union_list:
            required = False if state.is_optional_union_list else spec.is_required
        else:
            required = spec.is_required

        if kind is ArgumentKind.POSITIONAL and not required:
            self._validate_optional_positional(spec, state)

        return required

    @staticmethod
    def _validate_optional_positional(
        spec: ParamSpec,
        state: ArgumentBuildState,
    ) -> None:
        if state.value_shape is ValueShape.TUPLE:
            raise ConfigurationError(
                f"Optional tuple positional parameter '{spec.name}' is not supported"
            )

    def build_from_group(
        self,
        group: CommandGroup,
        parent_path: tuple[str, ...] = (),
        canonical_name: str | None = None,
        parent_settings: EffectiveCommandSettings | None = None,
        overrides: CommandOverrides | None = None,
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
        parameter_settings: dict[str, Param] | None = None,
    ) -> Command:
        """Build Command schema from a CommandGroup (manual construction)."""
        settings = self._resolve_effective_command_settings(
            parent_settings,
            overrides=overrides,
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
            initializer = self._build_args_from_source(
                group_args_source,
                settings=settings,
                parameter_settings=parameter_settings,
            )
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

        self._validate_positional_order(initializer, owner=cli_name)
        self._validate_optional_initializer_positionals(
            owner=cli_name,
            initializer=initializer,
            subcommands=subcommands,
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
            command_type="group",
            is_leaf=False,
            parent_path=parent_path,
            metadata={},
            parameter_settings=dict(parameter_settings or {}),
        )
        self._attach_command_build_settings(
            command,
            settings=settings,
            overrides=overrides,
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
        settings: EffectiveCommandSettings,
        parameter_settings: dict[str, Param] | None = None,
    ) -> list[Argument]:
        """Build argument list from a class __init__ or callable signature."""
        obj = inspect(source, init=True)
        resolve_objinspect_annotations(obj)

        taken_flags = [*self.context.reserved_flags]
        flag_state = FlagAllocationState()

        if isinstance(obj, Class) and obj.init_method:
            effective_parameter_settings = merge_parameter_settings(
                self._class_parameter_settings(obj),
                parameter_settings,
            )

            return [
                arg
                for param in obj.init_method.params
                for arg in self._argument_from_parameter(
                    param,
                    taken_flags,
                    set(),
                    settings=settings,
                    flag_allocation_state=flag_state,
                    parameter_setting=self._settings_for_param(effective_parameter_settings, param),
                )
            ]

        if isinstance(obj, Function):
            effective_parameter_settings = merge_parameter_settings(
                self._callable_parameter_settings(obj),
                parameter_settings,
            )

            return [
                arg
                for param in obj.params
                for arg in self._argument_from_parameter(
                    param,
                    taken_flags,
                    set(),
                    settings=settings,
                    flag_allocation_state=flag_state,
                    parameter_setting=self._settings_for_param(effective_parameter_settings, param),
                )
            ]

        return []

    def _build_command_entry(
        self,
        entry: CommandEntry,
        parent_path: tuple[str, ...],
        *,
        parent_settings: EffectiveCommandSettings,
    ) -> Command:
        """Build Command from a CommandEntry (function/class/instance)."""
        overrides = entry.overrides
        settings = self._resolve_effective_command_settings(parent_settings, overrides)
        if entry.is_instance:
            return self._build_from_instance(
                entry,
                parent_path,
                settings=settings,
                overrides=overrides,
                executable_flags=entry.executable_flags,
                help_group=entry.help_group,
                parameter_settings=entry.parameter_settings,
            )

        if isinstance(entry.obj, type):
            return self._build_from_class_recursive(
                entry,
                parent_path,
                settings=settings,
                overrides=overrides,
                executable_flags=entry.executable_flags,
                help_group=entry.help_group,
                parameter_settings=entry.parameter_settings,
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
                overrides=overrides,
                executable_flags=entry.executable_flags,
                help_group=entry.help_group,
                parameter_settings=entry.parameter_settings,
            )

        raise InvalidCommandError(entry.name)

    def _build_from_instance(
        self,
        entry: CommandEntry,
        parent_path: tuple[str, ...],
        *,
        settings: EffectiveCommandSettings,
        overrides: CommandOverrides | None = None,
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
        parameter_settings: dict[str, Param] | None = None,
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
                parameter_settings=parameter_settings,
            )

        cli_name = self.context.flag_strategy.command_translator.translate(entry.name)
        raw_description = entry.description or (cls.description if cls.has_docstring else None)
        resolved_executable_flags = list(executable_flags or [])
        self._validate_executable_flags_against_tokens(
            resolved_executable_flags,
            set(),
        )

        raw_epilog = None

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
            command_type="instance",
            is_leaf=False,
            is_instance=True,
            parent_path=parent_path,
            stored_instance=instance,
            metadata={},
            parameter_settings=dict(parameter_settings or {}),
        )
        self._attach_command_build_settings(
            command,
            settings=settings,
            overrides=overrides,
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
        settings: EffectiveCommandSettings,
        overrides: CommandOverrides | None = None,
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
        parameter_settings: dict[str, Param] | None = None,
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
        effective_parameter_settings = merge_parameter_settings(
            self._class_parameter_settings(cls),
            parameter_settings,
        )

        if init_params:
            init_pipe_names = init_pipe_config.targeted_parameters() if init_pipe_config else set()
            initializer = [
                arg
                for param in init_params
                for arg in self._argument_from_parameter(
                    param,
                    taken_flags,
                    init_pipe_names,
                    settings=settings,
                    flag_allocation_state=init_flag_state,
                    parameter_setting=self._settings_for_param(effective_parameter_settings, param),
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
                parameter_settings=parameter_settings,
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

        self._validate_positional_order(initializer, owner=cli_name)
        self._validate_optional_initializer_positionals(
            owner=cli_name,
            initializer=initializer,
            subcommands=subcommands,
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
            command_type="class",
            is_leaf=False,
            parent_path=parent_path,
            metadata={},
            parameter_settings=dict(effective_parameter_settings),
        )
        self._attach_command_build_settings(
            command,
            settings=settings,
            overrides=overrides,
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
    def _resolve_cli_name(
        override: str | None,
        canonical_name: str | None,
        fallback: str,
    ) -> str:
        return override or canonical_name or fallback


__all__ = ["ParserSchemaBuilder", "SchemaBuildContext"]

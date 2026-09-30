from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from inspect import Parameter as InspectParameter
from types import NoneType
from typing import Any

from objinspect import Parameter
from objinspect.typing import is_union_type, type_args

from interfacy.common.sentinels import MODEL_DEFAULT_UNSET
from interfacy.declarations.params import BooleanMode, Param
from interfacy.exceptions import ConfigurationError
from interfacy.introspection.annotations import resolve_type_alias, simplified_type_name
from interfacy.models import unwrap_optional
from interfacy.naming.flag_strategy import FlagAllocationState
from interfacy.schema.builder.context import (
    ArgumentBuildState,
    EffectiveCommandSettings,
    ParamSpec,
    SchemaBuildContext,
)
from interfacy.schema.builder.expansion import (
    ModelExpansionBuilder,
    ModelExpansionPredicate,
    should_expand_model_parameter,
)
from interfacy.schema.builder.flags import flags_for_parameter
from interfacy.schema.builder.settings import base_build_settings
from interfacy.schema.builder.states import (
    configure_typed_state,
    configure_var_positional_state,
    initial_argument_state,
)
from interfacy.schema.model import Argument, ArgumentDefault, ArgumentKind, ValueShape
from interfacy.schema.validation import validate_optional_positional_shape
from interfacy.schema.values import ValueCardinality

BUILTIN_TYPE_NAMES: dict[str, type] = {"bool": bool, "int": int, "float": float, "str": str}


@dataclass
class ArgumentBuilder:
    """Convert inspected parameters into schema arguments."""

    context: SchemaBuildContext

    def from_parameters(
        self,
        params: Sequence[Parameter],
        taken_flags: list[str],
        pipe_param_names: set[str] | None,
        *,
        settings: EffectiveCommandSettings,
        parameter_settings: dict[str, Param],
        descriptions: dict[str, str] | None = None,
    ) -> list[Argument]:
        """
        Build the arguments of one parameter list sharing a flag allocation state.

        Args:
            params (Sequence[Parameter]): Inspected parameters in declaration order.
            taken_flags (list[str]): Reserved flag keys, updated in place.
            pipe_param_names (set[str] | None): Parameters that accept piped input.
            settings (EffectiveCommandSettings): Effective command settings.
            parameter_settings (dict[str, Param]): Per-parameter settings by name.
            descriptions (dict[str, str] | None): Fallback descriptions by parameter name.
        """
        flag_state = FlagAllocationState()
        fallback_descriptions = descriptions or {}

        return [
            argument
            for param in params
            for argument in self.from_parameter(
                param,
                taken_flags,
                pipe_param_names,
                settings=settings,
                flag_allocation_state=flag_state,
                description_override=fallback_descriptions.get(param.name),
                parameter_setting=parameter_settings.get(param.name),
            )
        ]

    def from_parameter(
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
        """
        Build the arguments of one parameter; expanded models yield one per field.

        Args:
            param (Parameter): Inspected parameter.
            taken_flags (list[str]): Reserved flag keys, updated in place.
            pipe_param_names (set[str] | None): Parameters that accept piped input.
            settings (EffectiveCommandSettings | None): Effective command settings.
            flag_allocation_state (FlagAllocationState | None): Strategy allocation state.
            description_override (str | None): Description used when the parameter has none.
            parameter_setting (Param | None): Explicit parameter setting.
        """
        resolved_settings = settings or base_build_settings(self.context)
        annotation = normalize_parameter_annotation(param.type)
        if parameter_setting is not None and annotation is not bool:
            validate_non_boolean_setting(param.name, parameter_setting)

        if param.is_typed:
            model_type, is_optional_model = unwrap_optional(annotation)
            if self.should_expand_model(model_type, settings=resolved_settings):
                return self._expand_model_parameter(
                    param=param,
                    model_type=model_type,
                    is_optional_model=is_optional_model,
                    taken_flags=taken_flags,
                    settings=resolved_settings,
                    pipe_param_names=pipe_param_names,
                )

        translated_name = (
            self.context.flag_strategy.argument_translator.translate(param.name) or param.name
        )
        flags = flags_for_parameter(
            translated_name=translated_name,
            param=param,
            taken_flags=taken_flags,
            flag_allocation_state=flag_allocation_state,
            parameter_setting=parameter_setting,
            flag_strategy=self.context.flag_strategy,
            abbreviation_gen=self.context.abbreviation_gen,
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
            self.from_spec(
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

    def should_expand_model(self, param_type: Any, *, settings: EffectiveCommandSettings) -> bool:
        """
        Return whether a parameter type is expanded into per-field arguments.

        Args:
            param_type (Any): Parameter annotation.
            settings (EffectiveCommandSettings): Effective command settings.
        """
        return should_expand_model_parameter(
            param_type,
            type_parser=self.context.type_parser,
            expand_model_params=settings.expand_model_params,
        )

    def from_spec(
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
        """
        Build one argument from a normalized parameter spec and its allocated flags.

        Args:
            spec (ParamSpec): Normalized parameter description.
            translated_name (str): CLI display name.
            flags (tuple[str, ...]): Allocated flags; no dash prefix means positional.
            taken_flags (list[str]): Reserved flag keys, updated in place.
            pipe_param_names (set[str] | None): Parameters that accept piped input.
            allow_optional_union_list (bool): Whether `list[T] | None` makes it optional.
            suppress_parse_default (bool): Whether optional defaults are hidden from the parser.
            force_optional (bool): Whether the argument is never required.
            help_text (str | None): Help text overriding the spec description.
            is_expanded_from (str | None): Model parameter this argument was expanded from.
            expansion_path (tuple[str, ...]): Field path within the expanded model.
            original_model_type (type | None): Root model type of an expanded argument.
            parent_is_optional (bool): Whether the root model parameter is optional.
            model_default (Any): Default instance of the root model parameter.
            settings (EffectiveCommandSettings): Effective command settings.
            parameter_setting (Param | None): Explicit parameter setting.
        """
        state = initial_argument_state(spec)
        should_expand_model = self._model_predicate(settings)
        if spec.kind == InspectParameter.VAR_POSITIONAL:
            configure_var_positional_state(
                spec,
                state,
                type_parser=self.context.type_parser,
                should_expand_model=should_expand_model,
            )
        elif spec.is_typed:
            configure_typed_state(
                spec=spec,
                flags=flags,
                taken_flags=taken_flags,
                allow_optional_union_list=allow_optional_union_list,
                state=state,
                parameter_setting=parameter_setting,
                type_parser=self.context.type_parser,
                should_expand_model=should_expand_model,
                bool_negative_prefix=self.context.bool_negative_prefix,
            )

        if not spec.is_required and spec.is_typed and spec.type is not bool:
            state.argument_default = ArgumentDefault.present(spec.default)

        kind = argument_kind_from_flags(flags)
        accepts_stdin = pipe_param_names is not None and (
            spec.name in pipe_param_names
            or (is_expanded_from is not None and is_expanded_from in pipe_param_names)
        )
        required = required_for_spec(
            spec=spec,
            allow_optional_union_list=allow_optional_union_list,
            accepts_stdin=accepts_stdin,
            kind=kind,
            state=state,
        )
        if force_optional:
            required = False

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
            cardinality=argument_cardinality(spec, state, kind=kind, required=required),
            argument_default=argument_default,
            help=help_text if help_text is not None else spec.description,
            type=state.parsed_type,
            parser=state.parser_func,
            metavar=parameter_setting.metavar if parameter_setting is not None else None,
            boolean_behavior=state.boolean_behavior,
            choices=state.choices,
            accepts_stdin=accepts_stdin,
            pipe_required=accepts_stdin and spec.is_required,
            tuple_element_parsers=state.tuple_element_parsers,
            is_expanded_from=is_expanded_from,
            expansion_path=expansion_path,
            original_model_type=original_model_type,
            parent_is_optional=parent_is_optional,
            model_default=model_default,
            value_plan=state.value_plan,
        )

    def _model_predicate(self, settings: EffectiveCommandSettings) -> ModelExpansionPredicate:
        return lambda model: self.should_expand_model(model, settings=settings)

    def _expand_model_parameter(
        self,
        *,
        param: Parameter,
        model_type: type,
        is_optional_model: bool,
        taken_flags: list[str],
        settings: EffectiveCommandSettings,
        pipe_param_names: set[str] | None = None,
    ) -> list[Argument]:
        return ModelExpansionBuilder(
            flag_strategy=self.context.flag_strategy,
            abbreviation_gen=self.context.abbreviation_gen,
            nested_separator=getattr(self.context.flag_strategy, "nested_separator", "."),
            should_expand_model=self._model_predicate(settings),
            argument_factory=self.from_spec,
            param=param,
            taken_flags=taken_flags,
            settings=settings,
            pipe_param_names=pipe_param_names,
        ).build(model_type=model_type, is_optional_model=is_optional_model)


def normalize_parameter_annotation(annotation: Any) -> Any:
    """
    Resolve aliases, builtin type names, and `bool | None` to a buildable annotation.

    Args:
        annotation (Any): Raw parameter annotation.
    """
    annotation = resolve_type_alias(annotation)
    if isinstance(annotation, str):
        base_name = simplified_type_name(annotation).removesuffix("?")
        if base_name in BUILTIN_TYPE_NAMES:
            annotation = BUILTIN_TYPE_NAMES[base_name]

    if is_union_type(annotation):
        annotation_args = type_args(annotation)
        if len(annotation_args) == 2 and NoneType in annotation_args and bool in annotation_args:
            annotation = bool

    return annotation


def validate_non_boolean_setting(name: str, setting: Param) -> None:
    """
    Reject boolean-only options on a parameter setting for a non-boolean parameter.

    Args:
        name (str): Parameter name used in error messages.
        setting (Param): Parameter setting.

    Raises:
        ConfigurationError: The setting configures a boolean mode or negative flags.
    """
    if setting.boolean_mode is not BooleanMode.AUTO:
        raise ConfigurationError(
            f"Param.boolean_mode can only configure boolean parameter '{name}'"
        )
    if setting.negative_flags is not None:
        raise ConfigurationError(
            f"Param.negative_flags can only configure boolean parameter '{name}'"
        )


def argument_kind_from_flags(flags: tuple[str, ...]) -> ArgumentKind:
    """
    Return OPTION when any flag is dash-prefixed, otherwise POSITIONAL.

    Args:
        flags (tuple[str, ...]): Allocated flags.
    """
    if any(flag.startswith("-") for flag in flags):
        return ArgumentKind.OPTION

    return ArgumentKind.POSITIONAL


def required_for_spec(
    *,
    spec: ParamSpec,
    allow_optional_union_list: bool,
    accepts_stdin: bool,
    kind: ArgumentKind,
    state: ArgumentBuildState,
) -> bool:
    """
    Return whether the argument must be given on the command line.

    Args:
        spec (ParamSpec): Normalized parameter description.
        allow_optional_union_list (bool): Whether `list[T] | None` makes it optional.
        accepts_stdin (bool): Whether the argument can be filled from piped input.
        kind (ArgumentKind): Argument kind.
        state (ArgumentBuildState): Configured build state.

    Raises:
        ConfigurationError: An optional positional has an unsupported value shape.
    """
    if accepts_stdin:
        return False

    if allow_optional_union_list:
        required = False if state.is_optional_union_list else spec.is_required
    else:
        required = spec.is_required

    if kind is ArgumentKind.POSITIONAL and not required:
        validate_optional_positional_shape(spec.name, state.value_shape)

    return required


def argument_cardinality(
    spec: ParamSpec,
    state: ArgumentBuildState,
    *,
    kind: ArgumentKind,
    required: bool,
) -> ValueCardinality:
    """
    Return how many command-line tokens the argument consumes.

    Args:
        spec (ParamSpec): Normalized parameter description.
        state (ArgumentBuildState): Configured build state.
        kind (ArgumentKind): Argument kind.
        required (bool): Whether the argument is required.
    """
    if state.value_shape is ValueShape.FLAG:
        return ValueCardinality(0, 0, 0)

    if state.value_shape is ValueShape.LIST:
        item_size = state.cardinality.group_size
        min_count = 0 if spec.kind == InspectParameter.VAR_POSITIONAL or not required else item_size
        return ValueCardinality(min_count, None, item_size)

    if state.value_shape is ValueShape.TUPLE:
        if state.value_plan is not None:
            return state.value_plan.token_consumption(required=True)

        return state.cardinality

    minimum = 0 if kind is ArgumentKind.POSITIONAL and not required else 1

    return ValueCardinality(minimum, 1, 1)


__all__ = [
    "ArgumentBuilder",
    "argument_cardinality",
    "argument_kind_from_flags",
    "normalize_parameter_annotation",
    "required_for_spec",
    "validate_non_boolean_setting",
]

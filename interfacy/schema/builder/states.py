from __future__ import annotations

from typing import Any

from objinspect.typing import type_args

from interfacy.declarations.params import BooleanMode, Param
from interfacy.exceptions import ConfigurationError
from interfacy.introspection.annotations import (
    extract_optional_union_list,
    extract_optional_union_tuple,
    extract_union_list,
    get_fixed_tuple_info,
    is_fixed_tuple,
    is_list_or_list_alias,
)
from interfacy.introspection.choices import get_annotation_choices, get_param_choices
from interfacy.schema.builder.context import ArgumentBuildState, ParamSpec
from interfacy.schema.builder.expansion import ModelExpansionPredicate
from interfacy.schema.builder.flags import (
    generated_negative_flags,
    release_short_flags,
    reserve_parameter_flags,
)
from interfacy.schema.builder.plans import argument_value_plan, fixed_tuple_value_plan
from interfacy.schema.model import ArgumentDefault, BooleanBehavior, ValueShape
from interfacy.schema.values import (
    FlagValue,
    RepeatedValue,
    ScalarValue,
    UntypedValue,
    ValueCardinality,
    plan_requires_post_conversion,
)


def initial_argument_state(spec: ParamSpec) -> ArgumentBuildState:
    """
    Return the single-value build state of a parameter spec before type handling.

    Args:
        spec (ParamSpec): Normalized parameter description.
    """
    choices: tuple[Any, ...] | None = None
    if spec.is_typed and (raw_choices := get_param_choices(spec, for_display=False)):
        choices = tuple(raw_choices)

    return ArgumentBuildState(
        parser_func=None,
        value_shape=ValueShape.SINGLE,
        cardinality=ValueCardinality(1 if spec.is_required else 0, 1, 1),
        argument_default=(
            ArgumentDefault.present(spec.default) if spec.has_default else ArgumentDefault.absent()
        ),
        parsed_type=spec.type if spec.is_typed else None,
        choices=choices,
        boolean_behavior=None,
        value_plan=None,
    )


def configure_var_positional_state(
    spec: ParamSpec,
    state: ArgumentBuildState,
    *,
    type_parser: Any,
    should_expand_model: ModelExpansionPredicate,
) -> None:
    """
    Configure a `*args` parameter as a repeated positional value.

    Args:
        spec (ParamSpec): Normalized parameter description.
        state (ArgumentBuildState): Build state to update.
        type_parser (Any): Type parser providing parse functions.
        should_expand_model (ModelExpansionPredicate): Whether a model type is expanded.
    """
    state.value_shape = ValueShape.LIST
    state.cardinality = ValueCardinality(0, None, 1)
    state.argument_default = ArgumentDefault.present(())
    state.value_plan = RepeatedValue(
        argument_value_plan(spec.type, should_expand_model=should_expand_model)
        if spec.is_typed
        else UntypedValue()
    )
    if spec.is_typed:
        state.parsed_type = spec.type
        if spec.type is not str and not plan_requires_post_conversion(
            state.value_plan,
            required=spec.is_required,
        ):
            state.parser_func = type_parser.get_parse_func(spec.type)


def configure_typed_state(
    *,
    spec: ParamSpec,
    flags: tuple[str, ...],
    taken_flags: list[str],
    allow_optional_union_list: bool,
    state: ArgumentBuildState,
    parameter_setting: Param | None,
    type_parser: Any,
    should_expand_model: ModelExpansionPredicate,
    bool_negative_prefix: str | None,
) -> None:
    """
    Configure a typed parameter as a list, fixed tuple, boolean flag, or scalar value.

    Args:
        spec (ParamSpec): Normalized parameter description.
        flags (tuple[str, ...]): Allocated flags.
        taken_flags (list[str]): Reserved flag keys, updated in place.
        allow_optional_union_list (bool): Whether `list[T] | None` makes it optional.
        state (ArgumentBuildState): Build state to update.
        parameter_setting (Param | None): Explicit parameter setting.
        type_parser (Any): Type parser providing parse functions.
        should_expand_model (ModelExpansionPredicate): Whether a model type is expanded.
        bool_negative_prefix (str | None): Prefix for generated negative flags.
    """
    if configure_list_state(
        spec,
        allow_optional_union_list,
        state,
        type_parser=type_parser,
        should_expand_model=should_expand_model,
    ):
        return

    if configure_fixed_tuple_state(
        spec,
        state,
        type_parser=type_parser,
        should_expand_model=should_expand_model,
    ):
        return

    if configure_bool_state(
        spec,
        flags,
        taken_flags,
        state,
        parameter_setting,
        bool_negative_prefix=bool_negative_prefix,
    ):
        return

    configure_scalar_state(spec, state, type_parser=type_parser)


def configure_list_state(
    spec: ParamSpec,
    allow_optional_union_list: bool,
    state: ArgumentBuildState,
    *,
    type_parser: Any,
    should_expand_model: ModelExpansionPredicate,
) -> bool:
    """
    Configure a list annotation as a repeated value; return False for other types.

    Args:
        spec (ParamSpec): Normalized parameter description.
        allow_optional_union_list (bool): Whether `list[T] | None` makes it optional.
        state (ArgumentBuildState): Build state to update.
        type_parser (Any): Type parser providing parse functions.
        should_expand_model (ModelExpansionPredicate): Whether a model type is expanded.
    """
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
        argument_value_plan(
            element_type,
            should_expand_model=should_expand_model,
            allow_repeated=False,
        )
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
            state.parser_func = type_parser.get_parse_func(element_type)
    else:
        state.parsed_type = None
        state.parser_func = None

    if state.is_optional_union_list and not spec.has_default and allow_optional_union_list:
        state.argument_default = ArgumentDefault.present([])

    return True


def configure_fixed_tuple_state(
    spec: ParamSpec,
    state: ArgumentBuildState,
    *,
    type_parser: Any,
    should_expand_model: ModelExpansionPredicate,
) -> bool:
    """
    Configure a fixed-length tuple annotation; return False for other types.

    Args:
        spec (ParamSpec): Normalized parameter description.
        state (ArgumentBuildState): Build state to update.
        type_parser (Any): Type parser providing parse functions.
        should_expand_model (ModelExpansionPredicate): Whether a model type is expanded.
    """
    tuple_type = extract_optional_union_tuple(spec.type) or spec.type
    if not is_fixed_tuple(tuple_type):
        return False

    tuple_info = get_fixed_tuple_info(tuple_type)
    if tuple_info is None:
        return True

    element_count, element_types = tuple_info
    state.value_shape = ValueShape.TUPLE
    state.cardinality = ValueCardinality(element_count, element_count, element_count)
    tuple_plan = fixed_tuple_value_plan(spec.type, should_expand_model=should_expand_model)
    if tuple_plan is not None:
        state.value_plan = tuple_plan
        state.parser_func = None
        state.tuple_element_parsers = None
        state.parsed_type = spec.type
        state.cardinality = tuple_plan.token_consumption(required=spec.is_required)

        return True

    first_type = element_types[0]
    if all(t == first_type for t in element_types):
        state.parsed_type = first_type
        state.parser_func = type_parser.get_parse_func(first_type)
    else:
        state.tuple_element_parsers = tuple(type_parser.get_parse_func(t) for t in element_types)
        state.parsed_type = str
        state.parser_func = None

    return True


def configure_scalar_state(
    spec: ParamSpec,
    state: ArgumentBuildState,
    *,
    type_parser: Any,
) -> None:
    """
    Configure a single scalar value, leaving `Any` and `object` unparsed.

    Args:
        spec (ParamSpec): Normalized parameter description.
        state (ArgumentBuildState): Build state to update.
        type_parser (Any): Type parser providing parse functions.
    """
    if spec.type is Any or spec.type is object:
        state.value_plan = UntypedValue()
        state.parser_func = None

        return

    state.value_plan = ScalarValue(spec.type)
    if spec.type is not str:
        try:
            state.parser_func = type_parser.get_parse_func(spec.type)
        except TypeError:
            state.parser_func = None


def configure_bool_state(
    spec: ParamSpec,
    flags: tuple[str, ...],
    taken_flags: list[str],
    state: ArgumentBuildState,
    parameter_setting: Param | None,
    *,
    bool_negative_prefix: str | None,
) -> bool:
    """
    Configure a boolean flag's state and spellings; return False for non-booleans.

    Args:
        spec (ParamSpec): Normalized parameter description.
        flags (tuple[str, ...]): Allocated positive flags.
        taken_flags (list[str]): Reserved flag keys, updated in place.
        state (ArgumentBuildState): Build state to update.
        parameter_setting (Param | None): Explicit parameter setting.
        bool_negative_prefix (str | None): Prefix for generated negative flags.

    Raises:
        ConfigurationError: The boolean is positional or its mode or flags are invalid.
    """
    if spec.type is not bool:
        return False

    if not any(flag.startswith("-") for flag in flags):
        raise ConfigurationError(f"Boolean parameter '{spec.name}' must be an option")

    state.value_shape = ValueShape.FLAG
    state.value_plan = FlagValue()
    state.cardinality = ValueCardinality(0, 0, 0)
    state.argument_default = ArgumentDefault.present(spec.default if spec.has_default else False)
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
    mode = effective_boolean_mode(
        spec,
        requested_mode,
        configured_negative_flags,
        bool_negative_prefix=bool_negative_prefix,
    )

    positive_flags = flags if mode in {BooleanMode.POSITIVE_ONLY, BooleanMode.DUAL} else ()
    negative_flags: tuple[str, ...] = ()

    if mode is BooleanMode.NEGATIVE_ONLY:
        release_short_flags(flags, taken_flags)

    if mode is BooleanMode.POSITIVE_ONLY and configured_negative_flags is not None:
        raise ConfigurationError(
            f"Boolean parameter '{spec.name}' cannot define negative flags in positive_only mode"
        )

    if mode in {BooleanMode.NEGATIVE_ONLY, BooleanMode.DUAL}:
        negative_flags = configured_negative_flags or generated_negative_flags(
            spec.name,
            flags,
            bool_negative_prefix=bool_negative_prefix,
        )
        reserve_parameter_flags(negative_flags, taken_flags)

    state.boolean_behavior = BooleanBehavior(
        positive_flags=positive_flags,
        negative_flags=negative_flags,
        default=state.argument_default.value,
        mode=mode,
    )

    return True


def effective_boolean_mode(
    spec: ParamSpec,
    requested_mode: BooleanMode,
    configured_negative_flags: tuple[str, ...] | None,
    *,
    bool_negative_prefix: str | None,
) -> BooleanMode:
    """
    Return the boolean mode in effect, falling back to positive-only without negatives.

    Args:
        spec (ParamSpec): Normalized parameter description.
        requested_mode (BooleanMode): Mode requested by the parameter setting.
        configured_negative_flags (tuple[str, ...] | None): Explicit negative flags.
        bool_negative_prefix (str | None): Prefix for generated negative flags.
    """
    mode = resolve_boolean_mode(spec, requested_mode)

    if (
        bool_negative_prefix is None
        and configured_negative_flags is None
        and requested_mode is BooleanMode.AUTO
    ):
        return BooleanMode.POSITIVE_ONLY

    return mode


def resolve_boolean_mode(spec: ParamSpec, requested_mode: BooleanMode) -> BooleanMode:
    """
    Resolve AUTO from the default and check explicit modes against the default.

    Args:
        spec (ParamSpec): Normalized parameter description.
        requested_mode (BooleanMode): Mode requested by the parameter setting.

    Raises:
        ConfigurationError: An explicit mode contradicts the parameter default.
    """
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
            f"Boolean parameter '{spec.name}' uses positive_only mode but does not default to False"
        )
    if requested_mode is BooleanMode.NEGATIVE_ONLY and (
        not spec.has_default or spec.default is not True
    ):
        raise ConfigurationError(
            f"Boolean parameter '{spec.name}' uses negative_only mode but does not default to True"
        )

    return requested_mode


__all__ = [
    "configure_bool_state",
    "configure_fixed_tuple_state",
    "configure_list_state",
    "configure_scalar_state",
    "configure_typed_state",
    "configure_var_positional_state",
    "effective_boolean_mode",
    "initial_argument_state",
    "resolve_boolean_mode",
]

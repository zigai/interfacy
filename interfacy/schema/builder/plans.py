from __future__ import annotations

from typing import Any

from objinspect.typing import type_args

from interfacy.introspection.annotations import (
    extract_optional_union_list,
    extract_optional_union_tuple,
    extract_union_list,
    get_fixed_tuple_info,
    is_fixed_tuple,
    is_list_or_list_alias,
    resolve_type_alias,
)
from interfacy.models import model_fields_for_expansion, unwrap_optional
from interfacy.schema.builder.expansion import ModelExpansionPredicate
from interfacy.schema.values import (
    ArgumentValue,
    FixedTupleValue,
    FlagValue,
    ObjectFieldValue,
    ObjectValue,
    RepeatedValue,
    ScalarValue,
    UntypedValue,
)


def argument_value_plan(
    annotation: Any,
    *,
    should_expand_model: ModelExpansionPredicate,
    allow_repeated: bool = True,
) -> ArgumentValue:
    """
    Return the value plan that converts CLI tokens into a value of an annotation.

    Args:
        annotation (Any): Parameter or element annotation.
        should_expand_model (ModelExpansionPredicate): Whether a model type is built
            from positional field tokens.
        allow_repeated (bool): Whether list annotations become repeated values.
    """
    annotation = resolve_type_alias(annotation)
    if annotation is None:
        return UntypedValue()
    if annotation is bool:
        return FlagValue()

    optional_union_list = extract_optional_union_list(annotation)
    union_list = extract_union_list(annotation)
    if allow_repeated and (optional_union_list or union_list or is_list_or_list_alias(annotation)):
        if optional_union_list:
            _list_annotation, element_type = optional_union_list
        elif union_list:
            _list_annotation, element_type = union_list
        else:
            element_args = type_args(annotation)
            element_type = element_args[0] if element_args else None
        item_plan = (
            argument_value_plan(
                element_type,
                should_expand_model=should_expand_model,
                allow_repeated=False,
            )
            if element_type is not None
            else UntypedValue()
        )

        return RepeatedValue(item_plan)

    fixed_tuple_plan = fixed_tuple_value_plan(annotation, should_expand_model=should_expand_model)
    if fixed_tuple_plan is not None:
        return fixed_tuple_plan

    object_plan = object_value_plan(annotation, should_expand_model=should_expand_model)
    if object_plan is not None:
        return object_plan

    return ScalarValue(annotation)


def fixed_tuple_value_plan(
    annotation: Any,
    *,
    should_expand_model: ModelExpansionPredicate,
) -> FixedTupleValue | None:
    """
    Return a fixed-tuple plan when every element consumes a fixed number of tokens.

    Args:
        annotation (Any): Tuple annotation, optionally wrapped in an optional union.
        should_expand_model (ModelExpansionPredicate): Whether a model type is built
            from positional field tokens.
    """
    tuple_type = extract_optional_union_tuple(annotation) or annotation
    if not is_fixed_tuple(tuple_type):
        return None

    tuple_info = get_fixed_tuple_info(tuple_type)
    if tuple_info is None:
        return None

    _element_count, element_types = tuple_info
    item_plans = tuple(
        argument_value_plan(element_type, should_expand_model=should_expand_model)
        for element_type in element_types
    )
    if not all(value_plan_is_fixed(item) for item in item_plans):
        return None

    return FixedTupleValue(item_plans)


def object_value_plan(
    annotation: Any,
    *,
    should_expand_model: ModelExpansionPredicate,
) -> ObjectValue | None:
    """
    Return an object plan built from the required fields of a model annotation.

    Args:
        annotation (Any): Model annotation, optionally wrapped in an optional union.
        should_expand_model (ModelExpansionPredicate): Whether a model type is built
            from positional field tokens.
    """
    model_type, _is_optional_model = unwrap_optional(annotation)
    if not should_expand_model(model_type):
        return None

    fields: list[ObjectFieldValue] = []
    for field in model_fields_for_expansion(model_type):
        if not field.required:
            continue

        field_plan = argument_value_plan(field.annotation, should_expand_model=should_expand_model)
        if not value_plan_is_fixed(field_plan):
            return None

        fields.append(ObjectFieldValue(field.name, field_plan))

    if not fields:
        return None

    return ObjectValue(model_type, tuple(fields))


def value_plan_is_fixed(value_plan: ArgumentValue) -> bool:
    """
    Return whether a value plan consumes a fixed, non-zero number of tokens.

    Args:
        value_plan (ArgumentValue): Value plan to inspect.
    """
    consumption = value_plan.token_consumption(required=True)
    return consumption.is_fixed and consumption.group_size > 0


__all__ = [
    "argument_value_plan",
    "fixed_tuple_value_plan",
    "object_value_plan",
    "value_plan_is_fixed",
]

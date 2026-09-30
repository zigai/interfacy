from __future__ import annotations

from typing import Any

from interfacy.models.base import ModelAdapter, ModelField, unwrap_optional
from interfacy.models.dataclass import DataclassAdapter, dataclass_instance_values
from interfacy.models.plain import PlainClassAdapter, is_plain_class_model, plain_instance_values
from interfacy.models.pydantic import PydanticAdapter, dump_model_instance

DATACLASS_ADAPTER = DataclassAdapter()
PYDANTIC_ADAPTER = PydanticAdapter()
PLAIN_CLASS_ADAPTER = PlainClassAdapter()
MODEL_ADAPTERS: tuple[ModelAdapter, ...] = (
    DATACLASS_ADAPTER,
    PYDANTIC_ADAPTER,
    PLAIN_CLASS_ADAPTER,
)


def adapter_for(model_type: Any) -> ModelAdapter | None:
    """
    Return the first adapter that handles a model type.

    Args:
        model_type (Any): Candidate model type.
    """
    return next((adapter for adapter in MODEL_ADAPTERS if adapter.matches(model_type)), None)


def is_model_type(annotation: Any) -> bool:
    """
    Return whether an annotation is a supported model type.

    Args:
        annotation (Any): Candidate annotation object.
    """
    return isinstance(annotation, type) and adapter_for(annotation) is not None


def should_expand_model(param_type: Any, *, expand_model_params: bool = True) -> bool:
    """
    Return whether a parameter type should be flattened into CLI arguments.

    Args:
        param_type (Any): Parameter annotation to evaluate.
        expand_model_params (bool): Global switch enabling model expansion.
    """
    return expand_model_params and is_model_type(param_type)


def model_fields_for_expansion(model_type: type) -> list[ModelField]:
    """
    Return the constructor fields of a model type, or an empty list for non-models.

    Args:
        model_type (type): Model type to inspect.
    """
    adapter = adapter_for(model_type)
    if adapter is None:
        return []

    return adapter.fields(model_type)


def build_model_instance(model_type: type, values: dict[str, Any]) -> Any:
    """
    Construct a model instance from nested field values.

    Nested dictionaries are built into nested model instances. Values for types that
    are not models are returned unchanged.

    Args:
        model_type (type): Model type to construct.
        values (dict[str, Any]): Field values keyed by field name.
    """
    adapter = adapter_for(model_type)
    if adapter is None:
        return values

    return adapter.build_instance(model_type, values, coerce_model_value)


def coerce_model_value(annotation: Any, value: Any) -> Any:
    """
    Build nested model values and map empty optional models to None.

    Args:
        annotation (Any): Field annotation.
        value (Any): Raw field value.
    """
    if value is None:
        return None

    inner, is_optional = unwrap_optional(annotation)
    if isinstance(value, dict) and is_model_type(inner):
        if not value and is_optional:
            return None

        return build_model_instance(inner, value)

    return value


def model_instance_to_values(model_type: type, instance: Any) -> dict[str, Any]:
    """
    Return a model instance as nested field values.

    Args:
        model_type (type): Declared model type of the instance.
        instance (Any): Model instance, or None.
    """
    if instance is None:
        return {}

    if DATACLASS_ADAPTER.matches(model_type):
        return dataclass_instance_values(instance)

    dumped_values = dump_model_instance(instance)
    if dumped_values is not None:
        return dumped_values
    if hasattr(instance, "__dict__"):
        return instance_attribute_values(instance)
    if is_plain_class_model(model_type):
        return plain_instance_values(model_type, instance)

    return {}


def instance_attribute_values(instance: Any) -> dict[str, Any]:
    """
    Return instance attributes, converting nested model instances to values.

    Args:
        instance (Any): Object with a `__dict__`.
    """
    values: dict[str, Any] = {}
    for key, value in vars(instance).items():
        if is_model_type(type(value)):
            values[key] = model_instance_to_values(type(value), value)
        else:
            values[key] = value

    return values


__all__ = [
    "MODEL_ADAPTERS",
    "adapter_for",
    "build_model_instance",
    "coerce_model_value",
    "instance_attribute_values",
    "is_model_type",
    "model_fields_for_expansion",
    "model_instance_to_values",
    "should_expand_model",
]

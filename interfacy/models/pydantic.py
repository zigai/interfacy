from __future__ import annotations

from typing import Any

from interfacy.models.base import ModelField, ValueCoercer


class PydanticAdapter:
    """Model adapter for Pydantic v2 (`model_fields`) and v1 (`__fields__`) models."""

    def matches(self, model_type: Any) -> bool:
        """
        Return whether a type exposes Pydantic field metadata.

        Args:
            model_type (Any): Candidate model type.
        """
        return hasattr(model_type, "model_fields") or hasattr(model_type, "__fields__")

    def fields(self, model_type: type) -> list[ModelField]:
        """
        Return model fields, preferring the Pydantic v2 field map.

        Args:
            model_type (type): Pydantic model type.
        """
        if hasattr(model_type, "model_fields"):
            return pydantic_v2_fields(model_type)

        return pydantic_v1_fields(model_type)

    def build_instance(
        self,
        model_type: type,
        values: dict[str, Any],
        coerce: ValueCoercer,
    ) -> Any:
        """
        Construct a Pydantic model from declared field values.

        Args:
            model_type (type): Pydantic model type.
            values (dict[str, Any]): Field values keyed by field name.
            coerce (ValueCoercer): Coerces one field value against its annotation.
        """
        kwargs: dict[str, Any] = {}
        field_map = getattr(model_type, "model_fields", None) or getattr(
            model_type, "__fields__", {}
        )
        for name, info in field_map.items():
            if name not in values:
                continue

            annotation = getattr(info, "annotation", None)
            if annotation is None:
                annotation = getattr(info, "outer_type_", None) or getattr(info, "type_", None)

            kwargs[name] = coerce(annotation, values[name])

        return model_type(**kwargs)


def pydantic_v2_fields(model_type: type) -> list[ModelField]:
    """
    Return fields from a Pydantic v2 `model_fields` map.

    Args:
        model_type (type): Pydantic v2 model type.
    """
    result: list[ModelField] = []
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
            ModelField(
                name=name,
                annotation=annotation,
                required=required,
                default=default,
                description=getattr(info, "description", None),
            )
        )

    return result


def pydantic_v1_fields(model_type: type) -> list[ModelField]:
    """
    Return fields from a Pydantic v1 `__fields__` map.

    Args:
        model_type (type): Pydantic v1 model type.
    """
    result: list[ModelField] = []
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
            ModelField(
                name=name,
                annotation=annotation,
                required=required,
                default=default,
                description=description,
            )
        )

    return result


def dump_model_instance(instance: Any) -> dict[str, Any] | None:
    """
    Return field values from a v2 `model_dump()` or v1 `dict()` method, if available.

    Args:
        instance (Any): Model instance.
    """
    if hasattr(instance, "model_dump"):
        dumped = instance.model_dump()
        if isinstance(dumped, dict):
            return dumped

    if hasattr(instance, "dict"):
        dumped = instance.dict()
        if isinstance(dumped, dict):
            return dumped

    return None


__all__ = [
    "PydanticAdapter",
    "dump_model_instance",
    "pydantic_v1_fields",
    "pydantic_v2_fields",
]

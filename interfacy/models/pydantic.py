from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from interfacy.models.base import ModelField, ValueCoercer, resolved_type_hints


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
        alias_values: list[tuple[Sequence[str | int], Any]] = []
        field_map = getattr(model_type, "model_fields", None) or getattr(
            model_type, "__fields__", {}
        )
        is_v2 = hasattr(model_type, "model_fields")
        config = getattr(model_type, "model_config", {})
        for name, info in field_map.items():
            if name not in values:
                continue

            annotation = getattr(info, "annotation", None)
            if annotation is None:
                annotation = getattr(info, "outer_type_", None) or getattr(info, "type_", None)

            alias = getattr(info, "alias", None)
            if alias is None:
                alias = name
            if is_v2:
                if config.get("validate_by_alias", True):
                    validation_alias = getattr(info, "validation_alias", None)
                    if validation_alias is not None:
                        alias = validation_alias
                else:
                    alias = name
            choices = getattr(alias, "choices", None)
            if choices:
                alias = choices[0]
            path = [alias] if isinstance(alias, str) else alias.path
            alias_values.append((path, coerce(annotation, values[name])))

        return model_type(**build_alias_values(alias_values))


def build_alias_values(values: list[tuple[Sequence[str | int], Any]]) -> Any:
    if not values:
        return {}

    terminal_values = [value for path, value in values if not path]
    if terminal_values:
        if len(terminal_values) != len(values) or any(
            value != terminal_values[0] for value in terminal_values[1:]
        ):
            raise ValueError("Conflicting Pydantic validation alias paths")

        return terminal_values[0]

    keys = [path[0] for path, _ in values]
    is_list = isinstance(keys[0], int)
    if any(isinstance(key, int) != is_list for key in keys):
        raise ValueError("Conflicting Pydantic validation alias paths")

    size = (
        max(key + 1 if key >= 0 else -key for key in keys if isinstance(key, int)) if is_list else 0
    )
    grouped: dict[str | int, list[tuple[Sequence[str | int], Any]]] = {}
    for path, value in values:
        key = path[0]
        if isinstance(key, int) and key < 0:
            key += size
        grouped.setdefault(key, []).append((path[1:], value))

    if is_list:
        result: list[Any] = [None] * size
        for key, children in grouped.items():
            if isinstance(key, int):
                result[key] = build_alias_values(children)

        return result

    return {key: build_alias_values(children) for key, children in grouped.items()}


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
    hints = resolved_type_hints(model_type)
    field_map = getattr(model_type, "__fields__", {}) or {}
    for name, info in field_map.items():
        annotation = (
            hints.get(name) or getattr(info, "outer_type_", None) or getattr(info, "type_", None)
        )
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


__all__ = [
    "PydanticAdapter",
    "pydantic_v1_fields",
    "pydantic_v2_fields",
]

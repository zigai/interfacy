from __future__ import annotations

from collections.abc import Mapping
from dataclasses import MISSING, asdict, fields, is_dataclass
from typing import Any

from interfacy.models.base import (
    ModelField,
    ValueCoercer,
    parse_docstring_args,
    resolved_type_hints,
)


class DataclassAdapter:
    """Model adapter for standard library dataclasses."""

    def matches(self, model_type: Any) -> bool:
        """
        Return whether a type is a dataclass.

        Args:
            model_type (Any): Candidate model type.
        """
        return is_dataclass(model_type)

    def fields(self, model_type: type) -> list[ModelField]:
        """
        Return the init fields of a dataclass with metadata or docstring help.

        Args:
            model_type (type): Dataclass type.
        """
        arg_docs = parse_docstring_args(model_type.__doc__)
        hints = resolved_type_hints(model_type)
        result: list[ModelField] = []

        for field_info in fields(model_type):
            if not field_info.init:
                continue

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
                ModelField(
                    name=field_info.name,
                    annotation=hints.get(field_info.name, field_info.type),
                    required=required,
                    default=default,
                    description=description,
                )
            )

        return result

    def build_instance(
        self,
        model_type: type,
        values: dict[str, Any],
        coerce: ValueCoercer,
    ) -> Any:
        """
        Construct a dataclass from the provided init field values.

        Args:
            model_type (type): Dataclass type.
            values (dict[str, Any]): Field values keyed by field name.
            coerce (ValueCoercer): Coerces one field value against its annotation.
        """
        hints = resolved_type_hints(model_type)
        kwargs: dict[str, Any] = {}
        for field_info in fields(model_type):
            if field_info.init and field_info.name in values:
                annotation = hints.get(field_info.name, field_info.type)
                kwargs[field_info.name] = coerce(annotation, values[field_info.name])

        return model_type(**kwargs)


def dataclass_instance_values(instance: Any) -> dict[str, Any]:
    """
    Return a dataclass instance as nested field values.

    Args:
        instance (Any): Dataclass instance.
    """
    return asdict(instance)


__all__ = ["DataclassAdapter", "dataclass_instance_values"]

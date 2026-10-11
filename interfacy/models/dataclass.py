from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import MISSING, InitVar, fields, is_dataclass
from inspect import signature
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

        for name in signature(model_type).parameters:
            field_info = model_type.__dataclass_fields__.get(name)
            if field_info is None:
                continue
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

            annotation = hints.get(field_info.name, field_info.type)
            if isinstance(annotation, InitVar):
                annotation = annotation.type

            result.append(
                ModelField(
                    name=field_info.name,
                    annotation=annotation,
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
        kwargs: dict[str, Any] = {}
        for field_info in self.fields(model_type):
            if field_info.name in values:
                kwargs[field_info.name] = coerce(field_info.annotation, values[field_info.name])

        return model_type(**kwargs)


def dataclass_instance_values(instance: Any) -> dict[str, Any]:
    """
    Return a dataclass instance as nested field values.

    Args:
        instance (Any): Dataclass instance.
    """
    values: dict[str, Any] = {}
    for field_info in fields(instance):
        value = getattr(instance, field_info.name)
        values[field_info.name] = (
            dataclass_instance_values(value) if is_dataclass(value) else deepcopy(value)
        )

    return values


__all__ = ["DataclassAdapter", "dataclass_instance_values"]

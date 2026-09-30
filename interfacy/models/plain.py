from __future__ import annotations

import inspect
from collections.abc import Iterator
from typing import Any

from objinspect import Class, Parameter

from interfacy.models.base import ModelField, ValueCoercer, parse_docstring_args

OBJINSPECT_CLASS_ERRORS = (AttributeError, TypeError, ValueError)
BUILTIN_VALUE_TYPES = frozenset({str, int, float, bool, bytes, list, dict, tuple, set})


def plain_class_parameters(model_type: type) -> Iterator[Parameter]:
    """
    Yield the named `__init__` parameters of a regular class.

    Variadic parameters are skipped. Classes that cannot be inspected yield nothing.

    Args:
        model_type (type): Class to inspect.
    """
    try:
        cls_info = Class(
            model_type,
            init=True,
            public=True,
            inherited=True,
            static_methods=True,
            protected=False,
            private=False,
            classmethod=True,
        )
    except OBJINSPECT_CLASS_ERRORS:
        return

    init_method = cls_info.init_method
    if init_method is None:
        return

    for param in init_method.params:
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue

        yield param


def is_plain_class_model(annotation: Any) -> bool:
    """
    Return whether a regular class should be treated as a model type.

    Args:
        annotation (Any): Candidate annotation object.
    """
    if not isinstance(annotation, type):
        return False

    if annotation in BUILTIN_VALUE_TYPES:
        return False

    return next(plain_class_parameters(annotation), None) is not None


def plain_class_param_annotations(model_type: type) -> dict[str, Any]:
    """
    Return `__init__` parameter annotations keyed by parameter name.

    Args:
        model_type (type): Class to inspect.
    """
    return {
        param.name: param.type if param.is_typed else None
        for param in plain_class_parameters(model_type)
    }


def plain_class_fields(model_type: type) -> list[ModelField]:
    """
    Return `__init__` parameters as model fields with docstring help.

    Args:
        model_type (type): Class to inspect.
    """
    class_docs = parse_docstring_args(model_type.__doc__)
    return [
        ModelField(
            name=param.name,
            annotation=param.type if param.is_typed else None,
            required=param.is_required,
            default=param.default if param.has_default else None,
            description=param.description or class_docs.get(param.name),
        )
        for param in plain_class_parameters(model_type)
    ]


def plain_instance_values(model_type: type, instance: Any) -> dict[str, Any]:
    """
    Return attribute values of an instance that match `__init__` parameter names.

    Args:
        model_type (type): Class whose `__init__` parameters name the fields.
        instance (Any): Instance to read.
    """
    values: dict[str, Any] = {}
    for key in plain_class_param_annotations(model_type):
        if not hasattr(instance, key):
            continue

        values[key] = getattr(instance, key)

    return values


class PlainClassAdapter:
    """Model adapter for regular classes with named `__init__` parameters."""

    def matches(self, model_type: Any) -> bool:
        """
        Return whether a type is a regular class usable as a model.

        Args:
            model_type (Any): Candidate model type.
        """
        return is_plain_class_model(model_type)

    def fields(self, model_type: type) -> list[ModelField]:
        """
        Return `__init__` parameters as model fields.

        Args:
            model_type (type): Class to inspect.
        """
        return plain_class_fields(model_type)

    def build_instance(
        self,
        model_type: type,
        values: dict[str, Any],
        coerce: ValueCoercer,
    ) -> Any:
        """
        Construct a class instance from keyword arguments.

        Args:
            model_type (type): Class to construct.
            values (dict[str, Any]): Constructor values keyed by parameter name.
            coerce (ValueCoercer): Coerces one field value against its annotation.
        """
        annotations = plain_class_param_annotations(model_type)
        kwargs = {key: coerce(annotations.get(key), value) for key, value in values.items()}

        return model_type(**kwargs)


__all__ = [
    "PlainClassAdapter",
    "is_plain_class_model",
    "plain_class_fields",
    "plain_class_param_annotations",
    "plain_class_parameters",
    "plain_instance_values",
]

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import NoneType
from typing import Any, Protocol, get_type_hints

from objinspect.typing import is_union_type, type_args

from interfacy.introspection.annotations import resolve_type_alias

ValueCoercer = Callable[[Any, Any], Any]


@dataclass(frozen=True)
class ModelField:
    """
    One constructor field of a model type, as seen by CLI expansion.

    Attributes:
        name (str): Field name accepted by the model constructor.
        annotation (Any): Field annotation, or None when untyped.
        required (bool): Whether the constructor requires the field.
        default (Any): Default value or default factory for optional fields.
        description (str | None): Field help text.
    """

    name: str
    annotation: Any
    required: bool
    default: Any = None
    description: str | None = None


class ModelAdapter(Protocol):
    """Field discovery and construction for one kind of model type."""

    def matches(self, model_type: Any) -> bool:
        """
        Return whether this adapter handles a model type.

        Args:
            model_type (Any): Candidate model type.
        """
        ...

    def fields(self, model_type: type) -> list[ModelField]:
        """
        Return the constructor fields of a model type.

        Args:
            model_type (type): Model type handled by this adapter.
        """
        ...

    def build_instance(
        self,
        model_type: type,
        values: dict[str, Any],
        coerce: ValueCoercer,
    ) -> Any:
        """
        Construct a model instance from nested field values.

        Args:
            model_type (type): Model type handled by this adapter.
            values (dict[str, Any]): Field values keyed by field name.
            coerce (ValueCoercer): Coerces one field value against its annotation.
        """
        ...


def unwrap_optional(annotation: Any) -> tuple[Any, bool]:
    """
    Strip `None` from a simple optional union annotation.

    Args:
        annotation (Any): Raw annotation object or type alias.
    """
    annotation = resolve_type_alias(annotation)
    if not is_union_type(annotation):
        return annotation, False

    union_args = type_args(annotation)
    if NoneType not in union_args or len(union_args) != 2:
        return annotation, False

    inner = next(arg for arg in union_args if arg is not NoneType)

    return inner, True


def parse_docstring_args(docstring: str | None) -> dict[str, str]:
    """
    Return argument descriptions documented in a docstring.

    Args:
        docstring (str | None): Docstring to parse.
    """
    if not docstring:
        return {}

    import docstring_parser

    parsed = docstring_parser.parse(docstring)

    return {
        param.arg_name: (param.description or "").strip()
        for param in parsed.params
        if param.arg_name
    }


def resolved_type_hints(model_type: type) -> dict[str, Any]:
    """
    Return evaluated type hints, or an empty mapping when they cannot be resolved.

    Args:
        model_type (type): Type whose annotations are evaluated.
    """
    try:
        return get_type_hints(model_type)
    except (AttributeError, NameError, TypeError):
        return {}


__all__ = [
    "ModelAdapter",
    "ModelField",
    "ValueCoercer",
    "parse_docstring_args",
    "resolved_type_hints",
    "unwrap_optional",
]

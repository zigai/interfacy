import ast
import re
from enum import Enum
from types import NoneType
from typing import Any, Literal

from objinspect.typing import get_choices as objinspect_get_choices
from objinspect.typing import get_literal_choices, is_union_type, type_args, type_origin

from interfacy.introspection.annotations import resolve_type_alias


def _normalize_enum_choices(choices: list[Any], *, for_display: bool) -> list[Any] | None:
    normalized: list[Any] = []
    for choice in choices:
        if choice is None:
            continue

        if isinstance(choice, Enum):
            if for_display:
                value = choice.value
                if isinstance(value, str):
                    normalized.append(value)
                else:
                    normalized.append(choice.name)
            else:
                normalized.append(choice.name)
        else:
            normalized.append(choice)

    return normalized or None


def _parse_literal_choices_from_string(annotation: str) -> list[Any] | None:
    match = re.search(r"Literal\[(.*)\]", annotation)
    if not match:
        return None

    inner = match.group(1).strip()
    if not inner:
        return None

    try:
        parsed = ast.literal_eval(f"({inner})")
    except (SyntaxError, TypeError, ValueError):
        return None

    if not isinstance(parsed, tuple):
        parsed = (parsed,)

    return [value for value in parsed if value is not None] or None


def _literal_choices_from_annotation(annotation: Any) -> list[Any] | None:
    if type_origin(annotation) is not Literal:
        return None

    try:
        raw = get_literal_choices(annotation)
    except (AttributeError, KeyError, NameError, TypeError, ValueError):
        return None

    if not raw:
        return None

    return [value for value in raw if value is not None] or None


def _objinspect_choices_from_annotation(annotation: Any, *, for_display: bool) -> list[Any] | None:
    try:
        raw = objinspect_get_choices(annotation)
    except (AttributeError, KeyError, NameError, TypeError, ValueError):
        return None

    if not raw:
        return None

    return _normalize_enum_choices(list(raw), for_display=for_display)


def _union_choices(resolved: Any, *, for_display: bool) -> list[Any] | None:
    args = [arg for arg in type_args(resolved) if arg is not NoneType]
    all_choices: list[Any] = []
    for arg in args:
        sub = get_annotation_choices(arg, for_display=for_display)
        if not sub:
            return None

        all_choices.extend(sub)

    return all_choices or None


def get_annotation_choices(annotation: Any, *, for_display: bool = False) -> list[Any] | None:
    """
    Return a normalized list of choices for a type annotation.

    Uses objinspect's choices detection and adds support for Literals and Enums.
    """
    if annotation is None:
        return None

    resolved = resolve_type_alias(annotation)
    if is_union_type(resolved):
        return _union_choices(resolved, for_display=for_display)

    if isinstance(resolved, type) and issubclass(resolved, Enum):
        return _normalize_enum_choices(list(resolved), for_display=for_display)

    if isinstance(resolved, str):
        return _parse_literal_choices_from_string(resolved)

    literal_choices = _literal_choices_from_annotation(resolved)
    if literal_choices:
        return literal_choices

    return _objinspect_choices_from_annotation(resolved, for_display=for_display)


def get_param_choices(param: Any, *, for_display: bool = False) -> list[Any] | None:
    """Return choices for an objinspect Parameter, falling back to inferred Enum types."""
    choices = get_annotation_choices(param.type, for_display=for_display)
    if choices:
        return choices

    inferred = None
    try:
        inferred = param.get_infered_type()
    except (AttributeError, KeyError, NameError, TypeError, ValueError):
        inferred = None

    if inferred is None and param.has_default:
        default = param.default
        if isinstance(default, Enum):
            inferred = type(default)

    if inferred is None:
        return None

    return get_annotation_choices(inferred, for_display=for_display)


__all__ = [
    "get_annotation_choices",
    "get_param_choices",
]

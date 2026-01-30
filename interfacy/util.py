import ast
import re
import typing
from collections.abc import Callable
from enum import Enum
from types import NoneType
from typing import Any, Literal

from objinspect.typing import get_choices as objinspect_get_choices
from objinspect.typing import get_literal_choices, is_union_type, type_args, type_origin
from objinspect.util import colored_type
from stdl.st import with_style

from interfacy import console


def simplified_type_name(name: str) -> str:
    """
    Make a readable type name for help output.

    - Drops module paths (e.g. typing.Optional -> Optional)
    - Removes surrounding quotes if present
    - Collapses Optional/Union with None into a trailing '?' (e.g. "str | None" -> "str?")
    """
    name = name.strip().strip("'\"")
    name = name.split(".")[-1]
    name = re.sub(r"\s+", " ", name)
    optional_suffix = False  # Handle Optional[...] and Union[..., None] forms

    match = re.fullmatch(r"Optional\[(.*)\]", name)  # Optional[T]
    if match:
        name = match.group(1)
        optional_suffix = True

    match = re.fullmatch(r"Union\[(.*)\]", name)  # Union[T, None] or Union[None, T]
    if match:
        args = [a.strip() for a in match.group(1).split(",")]
        if "None" in args and len(args) == 2:
            args = [a for a in args if a != "None"]
            name = args[0] if args else name
            optional_suffix = True

    if re.search(r"\|\s*None\b", name) or re.search(r"\bNone\s*\|", name):  # T | None or None | T
        name = re.sub(r"\s*\|\s*None\b", "", name)
        name = re.sub(r"\bNone\s*\|\s*", "", name)
        name = name.strip()
        optional_suffix = True

    name = name.strip()
    if optional_suffix and not name.endswith("?"):
        name += "?"
    return name


def is_list_or_list_alias(t: type) -> bool:
    if t is list:
        return True
    t_origin = type_origin(t)
    return t_origin is list


def is_fixed_tuple(t: type) -> bool:
    """
    Check if the type annotation is a fixed-length tuple (e.g., tuple[str, str]).

    Returns False for:
    - Variable-length tuples: tuple[int, ...]
    - Bare tuple without type args
    - Non-tuple types
    """
    t_origin = type_origin(t)
    if t_origin is not tuple:
        return False

    args = type_args(t)
    if not args:
        return False

    if len(args) == 2 and args[1] is Ellipsis:  # Variable-length tuple: tuple[T, ...]
        return False

    return True


def get_fixed_tuple_info(t: type) -> tuple[int, tuple[type, ...]] | None:
    """
    Extract information from a fixed-length tuple type annotation.

    Returns:
        A tuple of (element_count, element_types) for fixed-length tuples,
        or None if not a fixed-length tuple.

    Example:
        tuple[str, str] -> (2, (str, str))
        tuple[int, str, float] -> (3, (int, str, float))
    """
    if not is_fixed_tuple(t):
        return None

    args = type_args(t)
    return len(args), tuple(args)


def extract_optional_union_list(t: Any) -> tuple[Any, Any | None] | None:
    """
    If the annotation represents `list[T] | None` or `Optional[list[T]]`, return the list annotation together with its element type.
    Otherwise `None`.
    """
    if not is_union_type(t):
        return None

    union_args = type_args(t)
    if not any(arg is NoneType for arg in union_args):
        return None

    for arg in union_args:
        if is_list_or_list_alias(arg):
            element_args = type_args(arg)
            element_type = element_args[0] if element_args else None
            return arg, element_type
    return None


def resolve_type_alias(annotation: Any) -> Any:
    """Resolve PEP 695 type aliases to their underlying value when possible."""
    type_alias_type = getattr(typing, "TypeAliasType", None)
    if type_alias_type is None:
        return annotation

    while isinstance(annotation, type_alias_type):
        try:
            annotation = annotation.__value__
        except Exception:
            break
    return annotation


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
    except Exception:
        return None

    if not isinstance(parsed, tuple):
        parsed = (parsed,)

    return [value for value in parsed if value is not None] or None


def get_annotation_choices(annotation: Any, *, for_display: bool = False) -> list[Any] | None:
    """
    Return a normalized list of choices for a type annotation.

    Uses objinspect's choices detection and adds support for Literals and Enums.
    """
    if annotation is None:
        return None

    annotation = resolve_type_alias(annotation)

    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return _normalize_enum_choices(list(annotation), for_display=for_display)

    if isinstance(annotation, str):
        literal_choices = _parse_literal_choices_from_string(annotation)
        if literal_choices:
            return literal_choices
        return None

    if type_origin(annotation) is Literal:
        try:
            raw = get_literal_choices(annotation)
            if raw:
                return [value for value in raw if value is not None] or None
        except Exception:
            return None

    try:
        raw = objinspect_get_choices(annotation)
        if raw:
            normalized = _normalize_enum_choices(list(raw), for_display=for_display)
            if normalized:
                return normalized
    except Exception:
        return None

    return None


def get_param_choices(param: Any, *, for_display: bool = False) -> list[Any] | None:
    """Return choices for an objinspect Parameter, falling back to inferred Enum types."""
    choices = get_annotation_choices(getattr(param, "type", None), for_display=for_display)
    if choices:
        return choices

    inferred = None
    if hasattr(param, "get_infered_type"):
        try:
            inferred = param.get_infered_type()
        except Exception:
            inferred = None

    if inferred is None and getattr(param, "has_default", False):
        default = getattr(param, "default", None)
        if isinstance(default, Enum):
            inferred = type(default)

    if inferred is None:
        return None

    return get_annotation_choices(inferred, for_display=for_display)


def format_default_for_help(value: Any) -> str:
    if isinstance(value, Enum):
        raw = value.value
        if isinstance(raw, (str, int, float, bool)):
            return str(raw)
        return value.name
    return str(value)


def show_result(result: Any, handler: Callable = print) -> None:
    console.display_result(result, handler=handler)


def inverted_bool_flag_name(name: str, prefix: str = "no-") -> str:
    if name.startswith(prefix):
        return name[len(prefix) :]
    return prefix + name


def format_type_for_help(annotation: Any, style: Any) -> str:
    """
    Return a styled, readable type string for CLI help, handling:
    - string annotations (from postponed annotations)
    - Optional unions (X | None or Optional[X]) as "X?"
    - falling back gracefully if coloring fails
    """
    if isinstance(annotation, str):
        name = simplified_type_name(annotation)
        if name.endswith("?"):
            return with_style(name[:-1], style) + "?"
        return with_style(name, style)

    try:
        if is_union_type(annotation):  # Optional union types (T | None)
            args = list(type_args(annotation))
            if len(args) == 2 and any(a is NoneType for a in args):
                base = next((a for a in args if a is not NoneType), None)
                if base is None:
                    return with_style("Any", style) + "?"
                try:
                    base_str = colored_type(base, style)
                except Exception:
                    base_str = with_style(
                        simplified_type_name(getattr(base, "__name__", str(base))),
                        style,
                    )
                return f"{base_str}?"  # Color only the base type and leave '?' unstyled
    except Exception:
        pass

    try:
        return colored_type(annotation, style)
    except Exception:
        try:
            name = getattr(annotation, "__name__", str(annotation))
        except Exception:
            name = str(annotation)
        simple = simplified_type_name(name)
        if simple.endswith("?"):
            return with_style(simple[:-1], style) + "?"
        return with_style(simple, style)


__all__ = [
    "simplified_type_name",
    "is_list_or_list_alias",
    "is_fixed_tuple",
    "get_fixed_tuple_info",
    "extract_optional_union_list",
    "resolve_type_alias",
    "get_annotation_choices",
    "get_param_choices",
    "format_default_for_help",
    "show_result",
    "inverted_bool_flag_name",
    "format_type_for_help",
]

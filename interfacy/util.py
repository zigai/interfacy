import ast
import re
import typing
from collections.abc import Callable
from enum import Enum
from pathlib import PurePath
from types import NoneType
from typing import Any, Literal

from objinspect import Class, Function, Method, Parameter
from objinspect.typing import get_choices as objinspect_get_choices
from objinspect.typing import get_literal_choices, is_union_type, type_args, type_origin

from interfacy import console

_MISSING = object()
_PATH_DEFAULT_REPR_RE = re.compile(
    r"^(?:Path|PosixPath|WindowsPath|PurePath|PurePosixPath|PureWindowsPath)\((.+)\)$"
)


def simplified_type_name(name: str) -> str:
    """
    Make a readable type name for help output.

    - Drops module paths (e.g. typing.Optional -> Optional)
    - Removes surrounding quotes if present
    - Collapses Optional/Union with None into a trailing '?' (e.g. "str | None" -> "str?")
    """
    name = name.strip().strip("'\"")
    name = _strip_qualified_names(name)
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
    """
    Return True if the annotation represents a list type.

    Args:
        t (type): Type annotation to inspect.
    """
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

    return not (len(args) == 2 and args[1] is Ellipsis)  # Variable-length tuple: tuple[T, ...]


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


def extract_optional_union_list(t: object) -> tuple[object, object | None] | None:
    """
    If the annotation represents `list[T] | None` or `Optional[list[T]]`, return the list annotation together with its element type.
    Otherwise `None`.
    """
    if not is_union_type(t):
        return None

    union_args = type_args(t)
    if len(union_args) != 2 or not any(arg is NoneType for arg in union_args):
        return None

    for arg in union_args:
        if is_list_or_list_alias(arg):
            element_args = type_args(arg)
            element_type = element_args[0] if element_args else None
            return arg, element_type
    return None


def _consume_quoted_segment(text: str, start: int) -> int:
    quote = text[start]
    index = start + 1
    escaped = False
    while index < len(text):
        current = text[index]
        if escaped:
            escaped = False
        elif current == "\\":
            escaped = True
        elif current == quote:
            return index + 1
        index += 1
    return index


def _consume_dotted_identifier(text: str, start: int) -> int:
    index = start + 1
    while index < len(text) and (text[index].isalnum() or text[index] in {"_", "."}):
        index += 1
    return index


def _strip_qualified_names(name: str) -> str:
    """Drop module prefixes from dotted type identifiers while preserving literals."""
    parts: list[str] = []
    index = 0
    while index < len(name):
        ch = name[index]
        if ch in {"'", '"'}:
            end = _consume_quoted_segment(name, index)
            parts.append(name[index:end])
            index = end
            continue

        if ch.isalpha() or ch == "_":
            end = _consume_dotted_identifier(name, index)
            token = name[index:end]
            parts.append(token.split(".")[-1])
            index = end
            continue

        parts.append(ch)
        index += 1

    return "".join(parts)


def resolve_type_alias(annotation: object) -> object:
    """Resolve PEP 695 type aliases to their underlying value when possible."""
    type_alias_type = getattr(typing, "TypeAliasType", None)
    if type_alias_type is None:
        return annotation

    while isinstance(annotation, type_alias_type):
        value = _resolve_type_alias_value(annotation)
        if value is _MISSING:
            break
        annotation = value
    return annotation


def _resolve_type_alias_value(annotation: object) -> object:
    try:
        return annotation.__value__
    except (AttributeError, NameError, RecursionError, TypeError):
        return _MISSING


def _resolve_owner_localns(owner_cls: type | object | None) -> dict[str, Any] | None:
    if owner_cls is None:
        return None

    owner_type = owner_cls if isinstance(owner_cls, type) else type(owner_cls)
    localns = dict(vars(owner_type))
    localns.setdefault(owner_type.__name__, owner_type)
    return localns


def _resolve_callable_hints(
    fn: Callable[..., Any], *, owner_cls: type | object | None = None
) -> dict[str, Any] | None:
    globalns = getattr(fn, "__globals__", None)
    localns = _resolve_owner_localns(owner_cls)
    try:
        return typing.get_type_hints(
            fn,
            globalns=globalns,
            localns=localns,
            include_extras=True,
        )
    except TypeError:
        try:
            return typing.get_type_hints(fn, globalns=globalns, localns=localns)
        except (AttributeError, NameError, TypeError, ValueError):
            return None
    except (AttributeError, NameError, ValueError):
        return None


def _apply_hints(params: list[Parameter], hints: dict[str, Any]) -> None:
    for param in params:
        hint = hints.get(param.name, _MISSING)
        if hint is not _MISSING:
            param.type = hint


def _resolve_and_apply_hints(
    fn: Callable[..., Any], params: list[Parameter], *, owner_cls: type | object | None = None
) -> None:
    hints = _resolve_callable_hints(fn, owner_cls=owner_cls)
    if hints:
        _apply_hints(params, hints)


def resolve_objinspect_annotations(obj: Function | Method | Class) -> None:
    """Resolve string/forward-ref annotations for objinspect objects in-place."""
    if isinstance(obj, Function):
        _resolve_and_apply_hints(obj.func, obj.params)
        return

    if isinstance(obj, Method):
        _resolve_and_apply_hints(obj.func, obj.params, owner_cls=obj.cls)
        return

    if isinstance(obj, Class):
        if obj.init_method is not None:
            _resolve_and_apply_hints(
                obj.init_method.func, obj.init_method.params, owner_cls=obj.cls
            )

        for method in obj.methods:
            _resolve_and_apply_hints(method.func, method.params, owner_cls=obj.cls)


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


def _literal_choices_from_annotation(annotation: object) -> list[object] | None:
    if type_origin(annotation) is not Literal:
        return None

    try:
        raw = get_literal_choices(annotation)
    except (AttributeError, KeyError, NameError, TypeError, ValueError):
        return None

    if not raw:
        return None
    return [value for value in raw if value is not None] or None


def _objinspect_choices_from_annotation(
    annotation: object, *, for_display: bool
) -> list[object] | None:
    try:
        raw = objinspect_get_choices(annotation)
    except (AttributeError, KeyError, NameError, TypeError, ValueError):
        return None

    if not raw:
        return None
    return _normalize_enum_choices(list(raw), for_display=for_display)


def get_annotation_choices(annotation: object, *, for_display: bool = False) -> list[object] | None:
    """
    Return a normalized list of choices for a type annotation.

    Uses objinspect's choices detection and adds support for Literals and Enums.
    """
    if annotation is None:
        return None

    resolved = resolve_type_alias(annotation)

    if isinstance(resolved, type) and issubclass(resolved, Enum):
        return _normalize_enum_choices(list(resolved), for_display=for_display)

    if isinstance(resolved, str):
        return _parse_literal_choices_from_string(resolved)

    literal_choices = _literal_choices_from_annotation(resolved)
    if literal_choices:
        return literal_choices

    return _objinspect_choices_from_annotation(resolved, for_display=for_display)


def get_param_choices(param: Parameter, *, for_display: bool = False) -> list[object] | None:
    """Return choices for an objinspect Parameter, falling back to inferred Enum types."""
    choices = get_annotation_choices(getattr(param, "type", None), for_display=for_display)
    if choices:
        return choices

    inferred = None
    if hasattr(param, "get_infered_type"):
        try:
            inferred = param.get_infered_type()
        except (AttributeError, KeyError, NameError, TypeError, ValueError):
            inferred = None

    if inferred is None and getattr(param, "has_default", False):
        default = getattr(param, "default", None)
        if isinstance(default, Enum):
            inferred = type(default)

    if inferred is None:
        return None

    return get_annotation_choices(inferred, for_display=for_display)


def format_default_for_help(value: object) -> str:
    """
    Format a default value for display in help text.

    Args:
        value (Any): Default value to render.
    """
    if isinstance(value, Enum):
        raw = value.value
        if isinstance(raw, (str, int, float, bool)):
            return str(raw)
        return value.name
    if isinstance(value, PurePath):
        return repr(str(value))
    if isinstance(value, str):
        if value == "":
            return '""'
        match = _PATH_DEFAULT_REPR_RE.fullmatch(value.strip())
        if match is not None:
            try:
                parsed = ast.literal_eval(match.group(1))
            except (SyntaxError, ValueError):
                parsed = None
            if isinstance(parsed, str):
                return repr(parsed)
    return str(value)


def show_result(result: object, handler: Callable[[object], object | None] = print) -> None:
    """
    Display a result value using the shared console helpers.

    Args:
        result (Any): Result value to display.
        handler (Callable[[Any], Any]): Output handler for non-dict results.
    """
    console.display_result(result, handler=handler)


def inverted_bool_flag_name(name: str, prefix: str = "no-") -> str:
    """
    Return the inverted boolean flag name with a prefix toggle.

    Args:
        name (str): Base flag name.
        prefix (str): Prefix for the inverted form.
    """
    if name.startswith(prefix):
        return name[len(prefix) :]
    return prefix + name


def format_type_for_help(annotation: object, style: object, theme: object | None = None) -> str:
    """
    Return a styled, readable type string for CLI help.

    Handles:
    - string annotations (from postponed annotations)
    - Optional unions (X | None or Optional[X]) as "X?"
    - token-level styling when a theme provides dedicated type token styles
    - falling back gracefully if coloring fails
    """
    from interfacy.appearance.type_help import format_type_for_help as _format_type_for_help

    return _format_type_for_help(annotation, style, theme=theme)


__all__ = [
    "extract_optional_union_list",
    "format_default_for_help",
    "format_type_for_help",
    "get_annotation_choices",
    "get_fixed_tuple_info",
    "get_param_choices",
    "inverted_bool_flag_name",
    "is_fixed_tuple",
    "is_list_or_list_alias",
    "resolve_objinspect_annotations",
    "resolve_type_alias",
    "show_result",
    "simplified_type_name",
]

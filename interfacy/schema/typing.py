import ast
import functools
import operator
import re
import typing
from collections.abc import Callable, Iterator
from enum import Enum
from types import NoneType
from typing import Any, Literal

from objinspect import Class, Function, Method, Parameter
from objinspect.typing import get_choices as objinspect_get_choices
from objinspect.typing import get_literal_choices, is_union_type, type_args, type_origin

_MISSING = object()


def simplified_type_name(name: str) -> str:
    """
    Make a readable type name for help output.

    - Drops module paths (e.g. typing.Optional -> Optional)
    - Removes surrounding quotes if present
    - Collapses Optional/Union with None into a trailing '?' (e.g. "str | None" -> "str?")
    """
    tokens = list(_type_name_tokens(name.strip().strip("'\"")))
    optional_suffix = False

    optional_args = _generic_type_arguments(tokens, "Optional")
    if optional_args is not None and len(optional_args) == 1:
        tokens = optional_args[0]
        optional_suffix = True

    union_args = _generic_type_arguments(tokens, "Union")
    if union_args is not None and len(union_args) == 2:
        for index, argument in enumerate(union_args):
            if "".join(argument).strip() == "None":
                tokens = union_args[1 - index]
                optional_suffix = True
                break

    name = "".join(tokens).strip()
    union_parts = _split_type_tokens(tokens, "|")
    if union_parts is not None and len(union_parts) > 1:
        parts = ["".join(part) for part in union_parts]
        if any(part.strip() == "None" for part in parts):
            name = "|".join(part for part in parts if part.strip() != "None").strip()
            optional_suffix = True

    if optional_suffix and not name.endswith("?"):
        name += "?"

    return name


def is_list_or_list_alias(t: Any) -> bool:
    """
    Return True if the annotation represents a list type.

    Args:
        t (type): Type annotation to inspect.
    """
    if t is list:
        return True

    t_origin = type_origin(t)

    return t_origin is list


def is_fixed_tuple(t: Any) -> bool:
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


def get_fixed_tuple_info(t: Any) -> tuple[int, tuple[Any, ...]] | None:
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
    if len(union_args) != 2 or not any(arg is NoneType for arg in union_args):
        return None

    for arg in union_args:
        if is_list_or_list_alias(arg):
            element_args = type_args(arg)
            element_type = element_args[0] if element_args else None
            return arg, element_type

    return None


def extract_optional_union_tuple(t: Any) -> Any | None:
    """Return the tuple annotation from `tuple[...] | None`, otherwise None."""
    if not is_union_type(t):
        return None

    union_args = type_args(t)
    if len(union_args) != 2 or not any(arg is NoneType for arg in union_args):
        return None

    for arg in union_args:
        if is_fixed_tuple(arg):
            return arg

    return None


def extract_union_list(t: Any) -> tuple[Any, Any | None] | None:
    """Return a shared list shape from `list[T] | list[U]`, otherwise None."""
    if not is_union_type(t):
        return None

    union_args = type_args(t)
    list_args = [arg for arg in union_args if is_list_or_list_alias(arg)]
    if len(list_args) != len(union_args) or not list_args:
        return None

    element_types = []
    for arg in list_args:
        args = type_args(arg)
        if not args:
            return arg, None

        element_types.append(args[0])

    if len(element_types) == 1:
        return list_args[0], element_types[0]

    return list_args[0], functools.reduce(operator.or_, element_types)


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


def _type_name_tokens(name: str) -> Iterator[str]:
    """Normalize identifiers and whitespace while keeping each quoted span opaque."""
    index = 0
    while index < len(name):
        ch = name[index]
        if ch in {"'", '"'}:
            end = _consume_quoted_segment(name, index)
            yield name[index:end]
            index = end
            continue

        if ch.isalpha() or ch == "_":
            end = _consume_dotted_identifier(name, index)
            token = name[index:end]
            yield token.split(".")[-1]
            index = end
            continue

        if ch.isspace():
            yield " "
            index += 1
            while index < len(name) and name[index].isspace():
                index += 1

            continue

        yield ch
        index += 1


def _split_type_tokens(tokens: list[str], separator: str) -> list[list[str]] | None:
    """Split only outside balanced brackets; malformed expressions remain opaque."""
    parts: list[list[str]] = [[]]
    brackets: list[str] = []
    closing = {"[": "]", "(": ")", "{": "}"}
    for token in tokens:
        if token in closing:
            brackets.append(closing[token])
        elif token in closing.values():
            if not brackets or brackets.pop() != token:
                return None
        elif token == separator and not brackets:
            parts.append([])
            continue

        parts[-1].append(token)

    return None if brackets else parts


def _generic_type_arguments(tokens: list[str], name: str) -> list[list[str]] | None:
    if tokens[:2] != [name, "["] or tokens[-1:] != ["]"]:
        return None

    return _split_type_tokens(tokens[2:-1], ",")


def resolve_type_alias(annotation: Any) -> Any:
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


def normalize_basic_annotation(annotation: Any) -> Any:
    """Resolve aliases and the builtin string annotations supported by argument discovery."""
    annotation = resolve_type_alias(annotation)
    if not isinstance(annotation, str):
        return annotation

    simple_name = simplified_type_name(annotation)
    base_name = simple_name.removesuffix("?")
    builtin_map = {"bool": bool, "int": int, "float": float, "str": str}

    return builtin_map.get(base_name, annotation)


def _resolve_type_alias_value(annotation: Any) -> Any:
    try:
        return annotation.__value__
    except (AttributeError, NameError, RecursionError, TypeError):
        return _MISSING


def resolve_objinspect_annotations(obj: Function | Method | Class) -> None:
    """Resolve string/forward-ref annotations for objinspect objects in-place."""
    if isinstance(obj, Function):
        targets: list[tuple[Callable[..., Any], list[Parameter], type | Any | None]] = [
            (obj.func, obj.params, None)
        ]
    elif isinstance(obj, Method):
        targets = [(obj.func, obj.params, obj.cls)]
    else:
        targets = []
        if obj.init_method is not None:
            targets.append((obj.init_method.func, obj.init_method.params, obj.cls))

        for method in obj.methods:
            targets.append((method.func, method.params, obj.cls))

    for fn, params, owner_cls in targets:
        globalns = getattr(fn, "__globals__", None)
        localns = None
        if owner_cls is not None:
            owner_type = owner_cls if isinstance(owner_cls, type) else type(owner_cls)
            localns = dict(vars(owner_type))
            localns.setdefault(owner_type.__name__, owner_type)

        try:
            hints = typing.get_type_hints(
                fn,
                globalns=globalns,
                localns=localns,
                include_extras=True,
            )
        except (AttributeError, NameError, TypeError, ValueError):
            continue

        for param in params:
            hint = hints.get(param.name, _MISSING)
            if hint is not _MISSING:
                param.type = hint


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


def get_annotation_choices(annotation: Any, *, for_display: bool = False) -> list[Any] | None:
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
    "extract_optional_union_list",
    "extract_optional_union_tuple",
    "extract_union_list",
    "get_annotation_choices",
    "get_fixed_tuple_info",
    "get_param_choices",
    "is_fixed_tuple",
    "is_list_or_list_alias",
    "normalize_basic_annotation",
    "resolve_objinspect_annotations",
    "resolve_type_alias",
    "simplified_type_name",
]

import ast
import re
import typing
from collections.abc import Callable
from enum import Enum
from types import NoneType
from typing import Any, Literal

from objinspect import Class, Function, Method, Parameter
from objinspect.typing import get_choices as objinspect_get_choices
from objinspect.typing import get_literal_choices, is_union_type, type_args, type_origin
from stdl.st import with_style

from interfacy import console

_MISSING = object()
_TYPE_ALIAS_RESOLUTION_ERRORS = (AttributeError, NameError, RecursionError, TypeError)
_TYPE_HINT_RESOLUTION_ERRORS = (AttributeError, NameError, TypeError, ValueError)
_LITERAL_PARSE_ERRORS = (SyntaxError, TypeError, ValueError)
_INTROSPECTION_ERRORS = (AttributeError, KeyError, NameError, TypeError, ValueError)
_STRINGIFY_ERRORS = (RecursionError, TypeError, ValueError)
_STYLE_RENDER_ERRORS = (AttributeError, TypeError, ValueError)


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
    if not any(arg is NoneType for arg in union_args):
        return None

    for arg in union_args:
        if is_list_or_list_alias(arg):
            element_args = type_args(arg)
            element_type = element_args[0] if element_args else None
            return arg, element_type
    return None


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
    except _TYPE_ALIAS_RESOLUTION_ERRORS:
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
        except _TYPE_HINT_RESOLUTION_ERRORS:
            return None
    except _TYPE_HINT_RESOLUTION_ERRORS:
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
    except _LITERAL_PARSE_ERRORS:
        return None

    if not isinstance(parsed, tuple):
        parsed = (parsed,)

    return [value for value in parsed if value is not None] or None


def _literal_choices_from_annotation(annotation: object) -> list[object] | None:
    if type_origin(annotation) is not Literal:
        return None

    try:
        raw = get_literal_choices(annotation)
    except _INTROSPECTION_ERRORS:
        return None

    if not raw:
        return None
    return [value for value in raw if value is not None] or None


def _objinspect_choices_from_annotation(
    annotation: object, *, for_display: bool
) -> list[object] | None:
    try:
        raw = objinspect_get_choices(annotation)
    except _INTROSPECTION_ERRORS:
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
        except _INTROSPECTION_ERRORS:
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
    return _format_type_for_help(annotation, style, theme)


_TYPE_BRACKETS = frozenset("[](){}")
_TYPE_PUNCTUATION = frozenset({",", ":"})
_TYPE_OPERATORS = frozenset({"|", "?"})
_TYPE_KEYWORDS = frozenset(
    {
        "Annotated",
        "Any",
        "ClassVar",
        "Final",
        "Literal",
        "Never",
        "NoReturn",
        "None",
        "NoneType",
        "NotRequired",
        "Optional",
        "Required",
        "Self",
        "TypeAlias",
        "TypeGuard",
        "TypeVar",
        "Union",
    }
)


def _safe_style(text: str, style: object) -> str:
    try:
        return with_style(text, style)
    except _STYLE_RENDER_ERRORS:
        return text


def _stringify_type_for_help(annotation: object) -> str:
    if isinstance(annotation, str):
        return simplified_type_name(annotation)

    resolved = resolve_type_alias(annotation)
    optional_union_name = _stringify_optional_union_type(resolved)
    if optional_union_name is not None:
        return optional_union_name

    generic_type_name = _stringify_generic_type(resolved)
    if generic_type_name is not None:
        return generic_type_name

    return simplified_type_name(_stringify_fallback_type_name(resolved))


def _stringify_optional_union_type(annotation: object) -> str | None:
    try:
        if not is_union_type(annotation):
            return None
        args = list(type_args(annotation))
    except _INTROSPECTION_ERRORS:
        return None

    if len(args) != 2 or not any(arg is NoneType for arg in args):
        return None

    base = next((arg for arg in args if arg is not NoneType), None)
    if base is None:
        return "Any?"

    base_name = _stringify_type_for_help(base)
    if base_name.endswith("?"):
        return base_name
    return f"{base_name}?"


def _safe_stringify(value: object) -> str:
    try:
        return str(value)
    except _STRINGIFY_ERRORS:
        return object.__repr__(value)


def _stringify_generic_type(annotation: object) -> str | None:
    try:
        origin = type_origin(annotation)
        args = type_args(annotation)
    except _INTROSPECTION_ERRORS:
        return None

    if origin is None or not args:
        return None

    return simplified_type_name(_safe_stringify(annotation))


def _stringify_fallback_type_name(annotation: object) -> str:
    if isinstance(annotation, type):
        return annotation.__name__

    name = getattr(annotation, "__name__", None)
    if isinstance(name, str):
        return name

    return _safe_stringify(annotation)


def _consume_space(text: str, start: int) -> int:
    index = start + 1
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _consume_quoted_literal(text: str, start: int) -> int:
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
            index += 1
            break
        index += 1
    return index


def _consume_numeric_literal(text: str, start: int) -> int:
    index = start + 1
    while index < len(text) and (text[index].isdigit() or text[index] == "."):
        index += 1
    return index


def _consume_identifier(text: str, start: int) -> int:
    index = start + 1
    while index < len(text) and (text[index].isalnum() or text[index] in {"_", "."}):
        index += 1
    return index


def _next_type_token(type_text: str, start: int) -> tuple[str, str, int]:
    ch = type_text[start]
    kind = "other"
    value = ch
    next_index = start + 1

    if ch.isspace():
        next_index = _consume_space(type_text, start)
        kind = "space"
        value = type_text[start:next_index]
    elif ch in _TYPE_BRACKETS:
        kind = "bracket"
    elif ch in _TYPE_PUNCTUATION:
        kind = "punctuation"
    elif ch in _TYPE_OPERATORS:
        kind = "operator"
    elif ch in {"'", '"'}:
        next_index = _consume_quoted_literal(type_text, start)
        kind = "literal"
        value = type_text[start:next_index]
    elif ch.isdigit():
        next_index = _consume_numeric_literal(type_text, start)
        kind = "literal"
        value = type_text[start:next_index]
    elif ch.isalpha() or ch == "_":
        next_index = _consume_identifier(type_text, start)
        value = type_text[start:next_index]
        kind = "keyword" if value in _TYPE_KEYWORDS else "name"

    return kind, value, next_index


def _tokenize_type_text(type_text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    index = 0
    while index < len(type_text):
        kind, value, index = _next_type_token(type_text, index)
        tokens.append((kind, value))
    return tokens


def _resolve_type_token_styles(style: object, theme: object | None) -> dict[str, object]:
    def pick(name: str, fallback: object) -> object:
        if theme is not None and hasattr(theme, name):
            return getattr(theme, name)
        return fallback

    return {
        "name": style,
        "keyword": pick("type_keyword", style),
        "bracket": pick("type_bracket", style),
        "punctuation": pick("type_punctuation", style),
        "operator": pick("type_operator", style),
        "literal": pick("type_literal", style),
        "other": style,
    }


def _format_type_for_help(annotation: object, style: object, theme: object | None = None) -> str:
    type_text = _stringify_type_for_help(annotation)
    styles = _resolve_type_token_styles(style, theme)
    tokens = _tokenize_type_text(type_text)

    rendered: list[str] = []
    for kind, value in tokens:
        if kind == "space":
            rendered.append(value)
        else:
            rendered.append(_safe_style(value, styles.get(kind, style)))
    return "".join(rendered)


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

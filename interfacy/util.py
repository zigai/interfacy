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


def resolve_objinspect_annotations(obj: Function | Method | Class) -> None:
    """Resolve string/forward-ref annotations for objinspect objects in-place."""

    def resolve_callable_hints(
        fn: Callable, *, owner_cls: type | object | None = None
    ) -> dict[str, Any] | None:
        globalns = getattr(fn, "__globals__", None)
        localns: dict[str, Any] | None = None
        if owner_cls is not None:
            if not isinstance(owner_cls, type):
                owner_cls = type(owner_cls)
            localns = dict(vars(owner_cls))
            localns.setdefault(owner_cls.__name__, owner_cls)
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
            except Exception:
                return None
        except Exception:
            return None

    def apply_hints(params: list[Parameter], hints: dict[str, Any]) -> None:
        for param in params:
            if param.name in hints:
                param.type = hints[param.name]

    if isinstance(obj, Function):
        hints = resolve_callable_hints(obj.func)
        if hints:
            apply_hints(obj.params, hints)
        return

    if isinstance(obj, Method):
        hints = resolve_callable_hints(obj.func, owner_cls=obj.cls)
        if hints:
            apply_hints(obj.params, hints)
        return

    if isinstance(obj, Class):
        if obj.init_method is not None:
            hints = resolve_callable_hints(obj.init_method.func, owner_cls=obj.cls)
            if hints:
                apply_hints(obj.init_method.params, hints)

        for method in obj.methods:
            hints = resolve_callable_hints(method.func, owner_cls=obj.cls)
            if hints:
                apply_hints(method.params, hints)


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


def show_result(result: Any, handler: Callable = print) -> None:
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


def format_type_for_help(annotation: Any, style: Any, theme: Any | None = None) -> str:
    """
    Return a styled, readable type string for CLI help, handling:
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


def _safe_style(text: str, style: Any) -> str:
    try:
        return with_style(text, style)
    except Exception:
        return text


def _stringify_type_for_help(annotation: Any) -> str:
    if isinstance(annotation, str):
        return simplified_type_name(annotation)

    annotation = resolve_type_alias(annotation)

    try:
        if is_union_type(annotation):
            args = list(type_args(annotation))
            if len(args) == 2 and any(arg is NoneType for arg in args):
                base = next((arg for arg in args if arg is not NoneType), None)
                if base is None:
                    return "Any?"
                base_name = _stringify_type_for_help(base)
                if base_name.endswith("?"):
                    return base_name
                return f"{base_name}?"
    except Exception:
        pass

    try:
        origin = type_origin(annotation)
        args = type_args(annotation)
        if origin is not None and args:
            return simplified_type_name(str(annotation))
    except Exception:
        pass

    try:
        if isinstance(annotation, type):
            raw_name = annotation.__name__
        else:
            raw_name = str(annotation)
    except Exception:
        try:
            raw_name = getattr(annotation, "__name__", str(annotation))
        except Exception:
            raw_name = str(annotation)

    return simplified_type_name(raw_name)


def _tokenize_type_text(type_text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    i = 0
    length = len(type_text)

    while i < length:
        ch = type_text[i]

        if ch.isspace():
            j = i + 1
            while j < length and type_text[j].isspace():
                j += 1
            tokens.append(("space", type_text[i:j]))
            i = j
            continue

        if ch in _TYPE_BRACKETS:
            tokens.append(("bracket", ch))
            i += 1
            continue

        if ch in _TYPE_PUNCTUATION:
            tokens.append(("punctuation", ch))
            i += 1
            continue

        if ch in _TYPE_OPERATORS:
            tokens.append(("operator", ch))
            i += 1
            continue

        if ch in {"'", '"'}:
            quote = ch
            j = i + 1
            escaped = False
            while j < length:
                curr = type_text[j]
                if escaped:
                    escaped = False
                elif curr == "\\":
                    escaped = True
                elif curr == quote:
                    j += 1
                    break
                j += 1
            tokens.append(("literal", type_text[i:j]))
            i = j
            continue

        if ch.isdigit():
            j = i + 1
            while j < length and (type_text[j].isdigit() or type_text[j] == "."):
                j += 1
            tokens.append(("literal", type_text[i:j]))
            i = j
            continue

        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < length and (type_text[j].isalnum() or type_text[j] in {"_", "."}):
                j += 1
            value = type_text[i:j]
            token_kind = "keyword" if value in _TYPE_KEYWORDS else "name"
            tokens.append((token_kind, value))
            i = j
            continue

        tokens.append(("other", ch))
        i += 1

    return tokens


def _resolve_type_token_styles(style: Any, theme: Any | None) -> dict[str, Any]:
    def pick(name: str, fallback: Any) -> Any:
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


def _format_type_for_help(annotation: Any, style: Any, theme: Any | None = None) -> str:
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
    "simplified_type_name",
    "is_list_or_list_alias",
    "is_fixed_tuple",
    "get_fixed_tuple_info",
    "extract_optional_union_list",
    "resolve_type_alias",
    "resolve_objinspect_annotations",
    "get_annotation_choices",
    "get_param_choices",
    "format_default_for_help",
    "show_result",
    "inverted_bool_flag_name",
    "format_type_for_help",
]

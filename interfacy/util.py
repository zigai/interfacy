import re
from collections.abc import Callable
from types import NoneType
from typing import Any

from objinspect.typing import is_union_type, type_args, type_origin
from objinspect.util import colored_type
from stdl.st import with_style


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


def show_result(result: Any, handler: Callable = print) -> None:
    if isinstance(result, list):
        for i in result:
            handler(i)
    elif isinstance(result, dict):
        from pprint import pprint

        pprint(result)
    else:
        handler(result)


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
    "show_result",
    "inverted_bool_flag_name",
    "format_type_for_help",
]

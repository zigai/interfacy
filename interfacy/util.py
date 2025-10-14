from collections.abc import Callable
from types import NoneType
from typing import Any

from objinspect.typing import is_union_type, type_args, type_origin


def simplified_type_name(name: str) -> str:
    """Simplifies the type name by removing module paths and optional "None" union."""
    name = name.split(".")[-1]
    if "| None" in name:
        name = name.replace("| None", "").strip()
        name += "?"
    return name


def is_list_or_list_alias(t: type) -> bool:
    if t is list:
        return True
    t_origin = type_origin(t)
    return t_origin is list


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


__all__ = [
    "simplified_type_name",
    "is_list_or_list_alias",
    "extract_optional_union_list",
    "show_result",
    "inverted_bool_flag_name",
]

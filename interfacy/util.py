from typing import Any

from objinspect.typing import type_origin


def simplified_type_name(name: str) -> str:
    """Simplifies the type name by removing module paths and optional "None" union."""
    name = name.split(".")[-1]
    if "| None" in name:
        name = name.replace("| None", "").strip()
        name += "?"
    return name


def is_list_or_list_alias(t):
    if t is list:
        return True
    t_origin = type_origin(t)
    return t_origin is list


def show_result(result: Any, handler=print):
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
    "show_result",
    "inverted_bool_flag_name",
]

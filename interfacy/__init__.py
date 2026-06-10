from typing import Any

_EXPORTS = {
    "BooleanMode": ("interfacy.schema", "BooleanMode"),
    "CommandGroup": ("interfacy.group", "CommandGroup"),
    "ExecutableFlag": ("interfacy.executable_flag", "ExecutableFlag"),
    "Interfacy": ("interfacy.interfacy", "Interfacy"),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, export_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    from importlib import import_module

    return getattr(import_module(module_name), export_name)


__all__ = ["BooleanMode", "CommandGroup", "ExecutableFlag", "Interfacy"]

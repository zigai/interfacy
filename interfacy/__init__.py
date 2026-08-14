from typing import Any

_EXPORTS = {
    "BooleanMode": ("interfacy.parameters", "BooleanMode"),
    "ConfigurationError": ("interfacy.exceptions", "ConfigurationError"),
    "CommandGroup": ("interfacy.group", "CommandGroup"),
    "ExecutableFlag": ("interfacy.executable_flag", "ExecutableFlag"),
    "DuplicateCommandError": ("interfacy.exceptions", "DuplicateCommandError"),
    "DuplicatePluginError": ("interfacy.exceptions", "DuplicatePluginError"),
    "ExitCode": ("interfacy.runtime.exit_codes", "ExitCode"),
    "HelpRenderer": ("interfacy.help", "HelpRenderer"),
    "HelpStyle": ("interfacy.help", "HelpStyle"),
    "Interfacy": ("interfacy.interfacy", "Interfacy"),
    "InterfacyError": ("interfacy.exceptions", "InterfacyError"),
    "Param": ("interfacy.parameters", "Param"),
    "InvalidCommandError": ("interfacy.exceptions", "InvalidCommandError"),
    "params": ("interfacy.parameters", "params"),
    "PipeInputError": ("interfacy.exceptions", "PipeInputError"),
    "ReservedFlagError": ("interfacy.exceptions", "ReservedFlagError"),
    "UnsupportedParameterTypeError": (
        "interfacy.exceptions",
        "UnsupportedParameterTypeError",
    ),
    "UsageError": ("interfacy.exceptions", "UsageError"),
    "UNSET": ("interfacy.engine", "UNSET"),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, export_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    from importlib import import_module

    return getattr(import_module(module_name), export_name)


__all__ = [
    "UNSET",
    "BooleanMode",
    "CommandGroup",
    "ConfigurationError",
    "DuplicateCommandError",
    "DuplicatePluginError",
    "ExecutableFlag",
    "ExitCode",
    "HelpRenderer",
    "HelpStyle",
    "Interfacy",
    "InterfacyError",
    "InvalidCommandError",
    "Param",
    "PipeInputError",
    "ReservedFlagError",
    "UnsupportedParameterTypeError",
    "UsageError",
    "params",
]

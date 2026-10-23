from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from interfacy.app import Interfacy
    from interfacy.common.resources import ParsedArguments
    from interfacy.common.sentinels import UNSET
    from interfacy.declarations.executable_flags import ExecutableFlag
    from interfacy.declarations.groups import CommandGroup
    from interfacy.declarations.params import BooleanMode, Param, params
    from interfacy.exceptions import (
        CommandError,
        CommandImportError,
        ConfigurationError,
        DuplicateCommandError,
        DuplicatePluginError,
        InterfacyError,
        InvalidCommandError,
        ParseDiagnostic,
        PipeInputError,
        ReservedFlagError,
        UnsupportedParameterTypeError,
        UsageError,
    )
    from interfacy.help import DiagnosticLayout, HelpRenderer, HelpStyle
    from interfacy.runtime.exit_codes import ExitCode


_EXPORTS = {
    "BooleanMode": ("interfacy.declarations.params", "BooleanMode"),
    "ConfigurationError": ("interfacy.exceptions", "ConfigurationError"),
    "CommandError": ("interfacy.exceptions", "CommandError"),
    "CommandGroup": ("interfacy.declarations.groups", "CommandGroup"),
    "CommandImportError": ("interfacy.exceptions", "CommandImportError"),
    "ExecutableFlag": ("interfacy.declarations.executable_flags", "ExecutableFlag"),
    "DuplicateCommandError": ("interfacy.exceptions", "DuplicateCommandError"),
    "DuplicatePluginError": ("interfacy.exceptions", "DuplicatePluginError"),
    "ExitCode": ("interfacy.runtime.exit_codes", "ExitCode"),
    "DiagnosticLayout": ("interfacy.help", "DiagnosticLayout"),
    "ParseDiagnostic": ("interfacy.exceptions", "ParseDiagnostic"),
    "HelpRenderer": ("interfacy.help", "HelpRenderer"),
    "HelpStyle": ("interfacy.help", "HelpStyle"),
    "Interfacy": ("interfacy.app", "Interfacy"),
    "InterfacyError": ("interfacy.exceptions", "InterfacyError"),
    "Param": ("interfacy.declarations.params", "Param"),
    "ParsedArguments": ("interfacy.common.resources", "ParsedArguments"),
    "InvalidCommandError": ("interfacy.exceptions", "InvalidCommandError"),
    "params": ("interfacy.declarations.params", "params"),
    "PipeInputError": ("interfacy.exceptions", "PipeInputError"),
    "ReservedFlagError": ("interfacy.exceptions", "ReservedFlagError"),
    "UnsupportedParameterTypeError": (
        "interfacy.exceptions",
        "UnsupportedParameterTypeError",
    ),
    "UsageError": ("interfacy.exceptions", "UsageError"),
    "UNSET": ("interfacy.common.sentinels", "UNSET"),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, export_name = _EXPORTS[name]
    except KeyError as e:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from e

    from importlib import import_module

    return getattr(import_module(module_name), export_name)


__all__ = [
    "UNSET",
    "BooleanMode",
    "CommandError",
    "CommandGroup",
    "CommandImportError",
    "ConfigurationError",
    "DiagnosticLayout",
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
    "ParseDiagnostic",
    "ParsedArguments",
    "PipeInputError",
    "ReservedFlagError",
    "UnsupportedParameterTypeError",
    "UsageError",
    "params",
]

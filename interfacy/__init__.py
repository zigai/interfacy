from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from interfacy.app import Interfacy as Interfacy
    from interfacy.common.sentinels import UNSET as UNSET
    from interfacy.declarations.executable_flags import ExecutableFlag as ExecutableFlag
    from interfacy.declarations.groups import CommandGroup as CommandGroup
    from interfacy.declarations.params import BooleanMode as BooleanMode
    from interfacy.declarations.params import Param as Param
    from interfacy.declarations.params import params as params
    from interfacy.exceptions import ConfigurationError as ConfigurationError
    from interfacy.exceptions import DuplicateCommandError as DuplicateCommandError
    from interfacy.exceptions import DuplicatePluginError as DuplicatePluginError
    from interfacy.exceptions import InterfacyError as InterfacyError
    from interfacy.exceptions import InvalidCommandError as InvalidCommandError
    from interfacy.exceptions import PipeInputError as PipeInputError
    from interfacy.exceptions import ReservedFlagError as ReservedFlagError
    from interfacy.exceptions import UnsupportedParameterTypeError as UnsupportedParameterTypeError
    from interfacy.exceptions import UsageError as UsageError
    from interfacy.help import HelpRenderer as HelpRenderer
    from interfacy.help import HelpStyle as HelpStyle
    from interfacy.runtime.exit_codes import ExitCode as ExitCode


_EXPORTS = {
    "BooleanMode": ("interfacy.declarations.params", "BooleanMode"),
    "ConfigurationError": ("interfacy.exceptions", "ConfigurationError"),
    "CommandGroup": ("interfacy.declarations.groups", "CommandGroup"),
    "ExecutableFlag": ("interfacy.declarations.executable_flags", "ExecutableFlag"),
    "DuplicateCommandError": ("interfacy.exceptions", "DuplicateCommandError"),
    "DuplicatePluginError": ("interfacy.exceptions", "DuplicatePluginError"),
    "ExitCode": ("interfacy.runtime.exit_codes", "ExitCode"),
    "HelpRenderer": ("interfacy.help", "HelpRenderer"),
    "HelpStyle": ("interfacy.help", "HelpStyle"),
    "Interfacy": ("interfacy.app", "Interfacy"),
    "InterfacyError": ("interfacy.exceptions", "InterfacyError"),
    "Param": ("interfacy.declarations.params", "Param"),
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

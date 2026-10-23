from dataclasses import dataclass
from typing import Literal

DiagnosticKind = Literal[
    "unknown_command",
    "unknown_option",
    "missing_argument",
    "missing_value",
    "missing_subcommand",
    "invalid_choice",
    "invalid_type",
    "unexpected_argument",
    "usage",
]


@dataclass(frozen=True, kw_only=True)
class ParseDiagnostic:
    """Backend-neutral failure facts; tokens contain names, never rejected parameter values."""

    kind: DiagnosticKind
    command_path: tuple[str, ...] = ()
    argument: str | None = None
    token: str | None = None
    choices: tuple[str, ...] = ()
    expected: str | None = None
    message: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "command_path", tuple(self.command_path))
        object.__setattr__(self, "choices", tuple(self.choices))


class InterfacyError(Exception):
    """Base exception for Interfacy errors."""


class CommandError(Exception):
    """Raise from a command for a failure whose message is written for the user.

    ``run()`` prints the message, without chained causes, and exits with
    ``ExitCode.COMMAND_FAILED``. Other command exceptions print only their type.
    """


class InterfacyExit(BaseException):
    """Request a normal non-process exit from an embedded invocation."""

    def __init__(self, code: int = 0) -> None:
        self.code = code
        super().__init__(code)


class UnsupportedParameterTypeError(InterfacyError):
    """Raise when a parameter type is unsupported by the parser."""

    def __init__(self, t: type) -> None:
        self.param_t = t
        super().__init__(f"Parameter of type '{t}' is not supported")


class ReservedFlagError(InterfacyError):
    """Raise when a flag name collides with a reserved flag."""

    def __init__(self, flag: str) -> None:
        self.flag = flag
        super().__init__(f"Flag name '{flag}' is already reserved for a different flag")


class InvalidCommandError(InterfacyError):
    """Raise when a command name is not registered."""

    def __init__(self, command: str) -> None:
        self.command = command
        super().__init__(f"'{command}' is not a valid command")


class CommandImportError(InterfacyError):
    """Raise when the target of a command registered by import path cannot be loaded."""

    def __init__(self, command: str, target: str, error: BaseException) -> None:
        self.command = command
        self.target = target
        super().__init__(f"Cannot load command '{command}' from '{target}': {error}")


class DuplicateCommandError(InterfacyError):
    """Raise when a command name is registered more than once."""

    def __init__(self, command: str) -> None:
        self.command = command
        super().__init__(f"Duplicate command '{command}'")


class DuplicatePluginError(InterfacyError):
    """Raise when a plugin name is registered more than once."""

    def __init__(self, plugin: str) -> None:
        self.plugin = plugin
        super().__init__(f"Duplicate plugin '{plugin}'")


class ConfigurationError(InterfacyError):
    """Raise for invalid configuration values."""


class UsageError(InterfacyError):
    """Raise when command-line input cannot be parsed."""

    def __init__(
        self,
        message: str,
        *,
        usage: str | None = None,
        diagnostic: ParseDiagnostic | None = None,
        program: str | None = None,
        exit_code: int = 2,
    ) -> None:
        self.usage = usage
        self.diagnostic = diagnostic
        self.program = program
        self.exit_code = exit_code
        super().__init__(message)


class PipeInputError(InterfacyError):
    """Raise when piped stdin cannot be applied to parameters."""

    def __init__(self, parameter: str, message: str) -> None:
        self.parameter = parameter
        prefix = "stdin" if parameter == "stdin" else f"parameter '{parameter}'"
        super().__init__(f"Pipe input error for {prefix}: {message}")


__all__ = [
    "CommandError",
    "CommandImportError",
    "ConfigurationError",
    "DiagnosticKind",
    "DuplicateCommandError",
    "DuplicatePluginError",
    "InterfacyError",
    "InterfacyExit",
    "InvalidCommandError",
    "ParseDiagnostic",
    "PipeInputError",
    "ReservedFlagError",
    "UnsupportedParameterTypeError",
    "UsageError",
]

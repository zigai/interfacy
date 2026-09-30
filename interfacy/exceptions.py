class InterfacyError(Exception):
    """Base exception for Interfacy errors."""


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

    def __init__(self, message: str, *, usage: str | None = None) -> None:
        self.usage = usage
        super().__init__(message)


class PipeInputError(InterfacyError):
    """Raise when piped stdin cannot be applied to parameters."""

    def __init__(self, parameter: str, message: str) -> None:
        self.parameter = parameter
        prefix = "stdin" if parameter == "stdin" else f"parameter '{parameter}'"
        super().__init__(f"Pipe input error for {prefix}: {message}")


__all__ = [
    "ConfigurationError",
    "DuplicateCommandError",
    "DuplicatePluginError",
    "InterfacyError",
    "InterfacyExit",
    "InvalidCommandError",
    "PipeInputError",
    "ReservedFlagError",
    "UnsupportedParameterTypeError",
    "UsageError",
]

class InterfacyError(Exception):
    pass


class UnsupportedParameterTypeError(InterfacyError):
    def __init__(self, t: type) -> None:
        self.param_t = t
        super().__init__(f"Parameter of type '{t}' is not supported")


class ReservedFlagError(InterfacyError):
    def __init__(self, flag: str):
        self.flag = flag
        super().__init__(f"Flag name '{flag}' is already reserved for a different flag")


class InvalidCommandError(InterfacyError):
    def __init__(self, command: str) -> None:
        self.command = command
        super().__init__(f"'{command}' is not a valid command")


class DuplicateCommandError(InterfacyError):
    def __init__(self, command: str) -> None:
        self.command = command
        super().__init__(f"Duplicate command '{command}'")


class ConfigurationError(InterfacyError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class PipeInputError(InterfacyError):
    def __init__(self, parameter: str, message: str) -> None:
        self.parameter = parameter
        prefix = "stdin" if parameter == "stdin" else f"parameter '{parameter}'"
        super().__init__(f"Pipe input error for {prefix}: {message}")


class InterfacyInterrupted(InterfacyError):
    """Raised when the CLI is interrupted by user (Ctrl+C from terminal)."""

    pass


class CliError(InterfacyError):
    """Base exception for CLI-related errors."""


class InvalidTargetSyntaxError(CliError):
    """Raised when the target spec does not match the expected format."""


class TargetNotFoundError(CliError):
    """Raised when the target object or method cannot be found."""

    def __init__(
        self,
        target: str,
        source: str,
        available: list[str] | None = None,
    ) -> None:
        self.target = target
        self.source = source
        self.available = available or []
        super().__init__(f"Target '{target}' not found in '{source}'")


class TargetImportError(CliError):
    """Raised when a module or file cannot be imported."""

    def __init__(self, message: str) -> None:
        super().__init__(message)

from interfacy.exceptions import InterfacyError


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


__all__ = [
    "CliError",
    "InvalidTargetSyntaxError",
    "TargetImportError",
    "TargetNotFoundError",
]

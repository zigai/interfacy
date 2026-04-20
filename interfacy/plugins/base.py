from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from interfacy.core import InterfacyParser
    from interfacy.schema.schema import Argument, ParserSchema


class ParseFailureKind(str, Enum):
    """Kinds of recoverable parse failures supported by the plugin system."""

    MISSING_ARGUMENTS = "missing_arguments"
    MISSING_SUBCOMMAND = "missing_subcommand"


@dataclass(frozen=True)
class ArgumentRef:
    """Stable reference to one schema argument inside a parsed command bucket."""

    command_path: tuple[str, ...]
    name: str
    argument: Argument = field(compare=False, hash=False)


@dataclass(frozen=True)
class ParseFailure:
    """Structured recoverable parse failure emitted by Interfacy."""

    backend: str
    kind: ParseFailureKind
    message: str
    command_path: tuple[str, ...]
    command_depth: int
    missing_arguments: tuple[ArgumentRef, ...] = ()
    available_subcommands: tuple[str, ...] = ()
    raw_exception: BaseException | None = field(compare=False, hash=False, default=None)


@dataclass(frozen=True)
class ProvideArgumentValues:
    """Recovery action that injects values into a partial parsed namespace."""

    values: dict[ArgumentRef, Any] = field(default_factory=dict)
    subcommands: dict[tuple[str, ...], str] = field(default_factory=dict)


@dataclass(frozen=True)
class AbortRecovery:
    """Recovery action that aborts the current CLI invocation."""

    exit_code: int = 2
    message: str | None = None


RecoveryAction = ProvideArgumentValues | AbortRecovery


class InterfacyPlugin:
    """Base class for code-registered Interfacy plugins."""

    name: str | None = None

    def configure(self, _parser: InterfacyParser) -> None:
        """Configure a parser immediately after plugin registration."""

    def transform_schema(
        self,
        _parser: InterfacyParser,
        schema: ParserSchema,
    ) -> ParserSchema:
        """Transform a fully built parser schema before backend materialization."""
        return schema

    def recover_parse_failure(
        self,
        _parser: InterfacyParser,
        _failure: ParseFailure,
    ) -> RecoveryAction | None:
        """Optionally recover from a structured parse failure."""
        return None

    @property
    def plugin_name(self) -> str:
        """Return the unique parser-local name used for plugin registration."""
        explicit_name = self.name
        if explicit_name:
            return explicit_name
        return type(self).__name__


__all__ = [
    "AbortRecovery",
    "ArgumentRef",
    "InterfacyPlugin",
    "ParseFailure",
    "ParseFailureKind",
    "ProvideArgumentValues",
    "RecoveryAction",
]

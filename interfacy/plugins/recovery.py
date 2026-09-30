from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, TypeAlias

from interfacy.plugins.descriptors import ArgumentDescriptor
from interfacy.plugins.freeze import freeze


class ParseFailureKind(str, Enum):
    """Kinds of recoverable parse failures supported by the plugin system."""

    MISSING_ARGUMENTS = "missing_arguments"
    MISSING_SUBCOMMAND = "missing_subcommand"


@dataclass(slots=True, unsafe_hash=True)
class ArgumentRef:
    """Stable reference to one schema argument inside a parsed command bucket."""

    command_path: tuple[str, ...]
    name: str
    argument: ArgumentDescriptor = field(compare=False, hash=False)

    def __post_init__(self) -> None:
        self.command_path = tuple(self.command_path)


@dataclass(slots=True)
class ParseFailure:
    """Backend-neutral structured recoverable parse failure."""

    kind: ParseFailureKind
    message: str
    command_path: tuple[str, ...]
    command_depth: int
    missing_arguments: tuple[ArgumentRef, ...] = ()
    available_subcommands: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self.command_path = tuple(self.command_path)
        self.missing_arguments = tuple(self.missing_arguments)
        self.available_subcommands = tuple(self.available_subcommands)


@dataclass(slots=True)
class ProvideArgumentValues:
    """Recovery action that injects values into a partial parsed namespace."""

    values: Mapping[ArgumentRef, Any] = field(default_factory=dict)
    subcommands: Mapping[tuple[str, ...], str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        frozen_values: dict[ArgumentRef, Any] = {
            ref: freeze(value) for ref, value in self.values.items()
        }
        frozen_subcommands: dict[tuple[str, ...], str] = {
            tuple(path): command for path, command in self.subcommands.items()
        }
        self.values = MappingProxyType(frozen_values)
        self.subcommands = MappingProxyType(frozen_subcommands)


@dataclass(slots=True)
class AbortRecovery:
    """Recovery action that aborts the current CLI invocation."""

    exit_code: int = 2
    message: str | None = None


RecoveryAction: TypeAlias = ProvideArgumentValues | AbortRecovery


__all__ = [
    "AbortRecovery",
    "ArgumentRef",
    "ParseFailure",
    "ParseFailureKind",
    "ProvideArgumentValues",
    "RecoveryAction",
]

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from interfacy.declarations.settings import BackendName
from interfacy.plugins.descriptors import SchemaDescriptor
from interfacy.plugins.freeze import freeze


@dataclass(slots=True)
class ConfigureContext:
    """Registration-phase capabilities and metadata."""

    backend: BackendName
    metadata: Mapping[str, Any]
    register_type_parser: Callable[[type[Any], Callable[[str], Any]], None] = field(
        compare=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        self.metadata = freeze(self.metadata)


@dataclass(slots=True)
class BeforeParseContext:
    """Input snapshot visible before backend parsing."""

    backend: BackendName
    metadata: Mapping[str, Any]
    args: tuple[str, ...]

    def __post_init__(self) -> None:
        self.metadata = freeze(self.metadata)
        self.args = tuple(self.args)


@dataclass(slots=True)
class SchemaTransformContext:
    """Metadata visible while transforming the explicit mutable schema payload."""

    backend: BackendName
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        self.metadata = freeze(self.metadata)


@dataclass(slots=True)
class AfterParseContext:
    """Parse result snapshot visible to namespace transforms."""

    backend: BackendName
    metadata: Mapping[str, Any]
    schema: SchemaDescriptor
    args: tuple[str, ...]
    namespace: Mapping[str, Any]

    def __post_init__(self) -> None:
        self.metadata = freeze(self.metadata)
        self.args = tuple(self.args)
        self.namespace = freeze(self.namespace)


@dataclass(slots=True)
class HelpHookContext:
    """Help invocation snapshot visible to help plugins."""

    backend: BackendName
    metadata: Mapping[str, Any]
    program: str
    terminal_width: int
    command_path: tuple[str, ...]
    schema: SchemaDescriptor

    def __post_init__(self) -> None:
        self.metadata = freeze(self.metadata)
        self.command_path = tuple(self.command_path)


@dataclass(slots=True)
class ExecuteContext:
    """Invocation snapshot visible to execution wrappers."""

    backend: BackendName
    metadata: Mapping[str, Any]
    schema: SchemaDescriptor
    args: tuple[str, ...]
    namespace: Mapping[str, Any]

    def __post_init__(self) -> None:
        self.metadata = freeze(self.metadata)
        self.args = tuple(self.args)
        self.namespace = freeze(self.namespace)


@dataclass(slots=True)
class ParseFailureContext:
    """Partial parse snapshot visible during parse recovery."""

    backend: BackendName
    metadata: Mapping[str, Any]
    schema: SchemaDescriptor
    args: tuple[str, ...]
    namespace: Mapping[str, Any]

    def __post_init__(self) -> None:
        self.metadata = freeze(self.metadata)
        self.args = tuple(self.args)
        self.namespace = freeze(self.namespace)


@dataclass(slots=True)
class BackendPluginContext:
    """Explicit unstable access to a selected backend adapter and native parser."""

    backend: BackendName
    adapter: Any = field(compare=False, repr=False)
    native_parser: Any | None = field(default=None, compare=False, repr=False)


__all__ = [
    "AfterParseContext",
    "BackendPluginContext",
    "BeforeParseContext",
    "ConfigureContext",
    "ExecuteContext",
    "HelpHookContext",
    "ParseFailureContext",
    "SchemaTransformContext",
]

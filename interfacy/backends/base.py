from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, NoReturn, Protocol, TypeVar

from strto import StrToTypeParser

from interfacy.declarations.executable_flags import ExecutableAction, ExecutableFlag
from interfacy.declarations.settings import BackendName
from interfacy.help import HelpLayout
from interfacy.schema.model import ParserSchema

NativeParserT_co = TypeVar("NativeParserT_co", covariant=True)
NativePresentationKind = Literal["usage", "execution"]


def _freeze_namespace(namespace: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(namespace))


@dataclass(slots=True, kw_only=True)
class BackendConfig:
    program_name: str | None = None
    help_flags: tuple[str, ...] = ("--help",)
    tab_completion: bool = False
    allow_args_from_file: bool = True
    help_layout: HelpLayout | None = None
    type_parser: StrToTypeParser | None = None

    def __post_init__(self) -> None:
        self.help_flags = tuple(self.help_flags)


@dataclass(slots=True)
class ParseResult:
    """
    Namespace parsed from command-line arguments.

    Attributes:
        args (tuple[str, ...]): Arguments that were parsed.
        namespace (Mapping[str, object]): Parsed values, defaults included.
        supplied (Mapping[str, object]): ``namespace`` restricted to the keys given on the
            command line, with the same bucket structure. Only key presence is meaningful;
            values may not be converted.
    """

    args: tuple[str, ...]
    namespace: Mapping[str, object]
    supplied: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.args = tuple(self.args)
        self.namespace = _freeze_namespace(self.namespace)
        self.supplied = _freeze_namespace(self.supplied)


@dataclass(slots=True, kw_only=True)
class NativePresentation:
    kind: NativePresentationKind
    message: str
    command_path: tuple[str, ...] = ()
    exit_code: int = 2

    def __post_init__(self) -> None:
        self.command_path = tuple(self.command_path)
        if self.kind not in ("usage", "execution"):
            raise ValueError(f"Unsupported native presentation kind: {self.kind}")


@dataclass(slots=True, kw_only=True)
class BackendParseFailure:
    presentation: NativePresentation
    partial_namespace: Mapping[str, object]

    def __post_init__(self) -> None:
        self.partial_namespace = _freeze_namespace(self.partial_namespace)


ParseOutcome = ParseResult | BackendParseFailure | ExecutableAction


class HelpPipeline(Protocol):
    """Render help for a compiled command path without exposing native parser state."""

    def render(
        self,
        command_path: tuple[str, ...],
        terminal_width: int | None = None,
    ) -> str: ...


class BackendSession(Protocol[NativeParserT_co]):
    """Own one compiled native parser and all operations that require it."""

    @property
    def native_parser(self) -> NativeParserT_co: ...

    def parse(self, args: tuple[str, ...]) -> ParseOutcome:
        """Parse arguments or return a flag action without executing its handler."""
        ...

    def present_error(self, presentation: NativePresentation) -> NoReturn: ...


class BackendAdapter(Protocol[NativeParserT_co]):
    """Compile finalized neutral schemas into backend-owned sessions."""

    @property
    def name(self) -> BackendName: ...

    def compile(
        self,
        schema: ParserSchema,
        help_pipeline: HelpPipeline,
        backend_config: BackendConfig,
    ) -> BackendSession[NativeParserT_co]: ...


class ExecutableFlagTriggeredError(Exception):
    """Raised inside a backend parser when an executable flag must run instead of parsing."""

    def __init__(self, flag: ExecutableFlag) -> None:
        self.flag = flag
        super().__init__(flag.flags[0])


class BackendAdapterFactory(Protocol):
    """Create adapters while keeping concrete and optional imports behind the call."""

    def __call__(self, backend: BackendName) -> BackendAdapter[object]: ...


__all__ = [
    "BackendAdapter",
    "BackendAdapterFactory",
    "BackendConfig",
    "BackendParseFailure",
    "BackendSession",
    "ExecutableFlagTriggeredError",
    "HelpPipeline",
    "NativePresentation",
    "NativePresentationKind",
    "ParseOutcome",
    "ParseResult",
]

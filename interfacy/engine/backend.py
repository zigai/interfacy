from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, NoReturn, Protocol, TypeVar

from strto import StrToTypeParser

from interfacy.engine.settings import BackendName
from interfacy.exceptions import ConfigurationError
from interfacy.executable_flag import ExecutableAction
from interfacy.help.layout import HelpLayout
from interfacy.schema.schema import ParserSchema

NativeParserT_co = TypeVar("NativeParserT_co", covariant=True)
ParseMode = Literal["full", "partial"]
ParseDefaultPolicy = Literal["include", "suppress"]
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
class ParseRequest:
    args: tuple[str, ...]
    mode: ParseMode = "full"
    default_policy: ParseDefaultPolicy = "include"

    def __post_init__(self) -> None:
        self.args = tuple(self.args)
        if self.mode not in ("full", "partial"):
            raise ValueError(f"Unsupported parse mode: {self.mode}")
        if self.default_policy not in ("include", "suppress"):
            raise ValueError(f"Unsupported parse default policy: {self.default_policy}")


@dataclass(slots=True)
class ParseResult:
    args: tuple[str, ...]
    namespace: Mapping[str, object]
    remaining_args: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self.args = tuple(self.args)
        self.namespace = _freeze_namespace(self.namespace)
        self.remaining_args = tuple(self.remaining_args)


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
    request: ParseRequest
    presentation: NativePresentation
    partial_namespace: Mapping[str, object]
    remaining_args: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self.partial_namespace = _freeze_namespace(self.partial_namespace)
        self.remaining_args = tuple(self.remaining_args)


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

    def parse(self, request: ParseRequest) -> ParseOutcome:
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


class BackendAdapterFactory(Protocol):
    """Create adapters while keeping concrete and optional imports behind the call."""

    def __call__(self, backend: BackendName) -> BackendAdapter[object]: ...


def create_backend_adapter(backend: BackendName) -> BackendAdapter[object]:
    if backend == "argparse":
        from interfacy.argparse_backend.adapter import ArgparseBackend

        return ArgparseBackend()

    if backend != "click":
        raise ConfigurationError("backend must be one of: argparse, click")

    try:
        from interfacy.click_backend.adapter import ClickBackend
    except ImportError as e:
        if not _is_missing_click(e):
            raise

        raise ImportError(
            "Click is required to use Interfacy with backend='click'. Install it with "
            "\"pip install 'interfacy[click]'\" or \"uv add 'interfacy[click]'\"."
        ) from e

    return ClickBackend()


def _is_missing_click(error: BaseException) -> bool:
    """Recognize an absent Click package through an import failure's visible chain."""
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))

        if isinstance(current, ModuleNotFoundError) and current.name == "click":
            return True

        current = (
            current.__cause__
            if current.__suppress_context__
            else current.__cause__ or current.__context__
        )

    return False


__all__ = [
    "BackendAdapter",
    "BackendAdapterFactory",
    "BackendConfig",
    "BackendParseFailure",
    "BackendSession",
    "ExecutableAction",
    "HelpPipeline",
    "NativePresentation",
    "NativePresentationKind",
    "ParseDefaultPolicy",
    "ParseMode",
    "ParseOutcome",
    "ParseRequest",
    "ParseResult",
    "create_backend_adapter",
]

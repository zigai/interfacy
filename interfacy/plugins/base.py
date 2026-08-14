from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, ClassVar, Literal, TypeAlias

from interfacy.help.content import HelpContent, HelpResult
from interfacy.schema.schema import ParserSchema

BackendName: TypeAlias = Literal["argparse", "click"]


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class ConfigureContext:
    """Registration-phase capabilities and metadata."""

    backend: BackendName
    metadata: Mapping[str, Any]
    register_type_parser: Callable[[type[Any], Callable[[str], Any]], None] = field(
        compare=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze(self.metadata))


@dataclass(frozen=True)
class BeforeParseContext:
    """Immutable input visible before backend parsing."""

    backend: BackendName
    metadata: Mapping[str, Any]
    args: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze(self.metadata))
        object.__setattr__(self, "args", tuple(self.args))


@dataclass(frozen=True)
class SchemaTransformContext:
    """Metadata visible while transforming the explicit mutable schema payload."""

    backend: BackendName
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze(self.metadata))


@dataclass(frozen=True)
class ArgumentDescriptor:
    """Backend-neutral immutable description of a schema argument."""

    command_path: tuple[str, ...]
    name: str
    display_name: str
    kind: str
    value_shape: str
    flags: tuple[str, ...]
    required: bool
    type: type[Any] | None
    choices: tuple[Any, ...] | None = field(default=None, compare=False, hash=False)
    metadata: Mapping[str, Any] = field(
        default_factory=dict,
        compare=False,
        hash=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "command_path", tuple(self.command_path))
        object.__setattr__(self, "flags", tuple(self.flags))
        object.__setattr__(
            self,
            "choices",
            _freeze(self.choices) if self.choices is not None else None,
        )
        object.__setattr__(self, "metadata", _freeze(self.metadata))


@dataclass(frozen=True)
class SchemaDescriptor:
    """Small immutable snapshot shared by read-only plugin phases."""

    description: str | None
    epilog: str | None
    command_paths: tuple[tuple[str, ...], ...]
    arguments: tuple[ArgumentDescriptor, ...]
    metadata: Mapping[str, Any] = field(
        default_factory=dict,
        compare=False,
        hash=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "command_paths",
            tuple(tuple(path) for path in self.command_paths),
        )
        object.__setattr__(self, "arguments", tuple(self.arguments))
        object.__setattr__(self, "metadata", _freeze(self.metadata))


@dataclass(frozen=True)
class AfterParseContext:
    """Immutable parse result state visible to namespace transforms."""

    backend: BackendName
    metadata: Mapping[str, Any]
    schema: SchemaDescriptor
    args: tuple[str, ...]
    namespace: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze(self.metadata))
        object.__setattr__(self, "args", tuple(self.args))
        object.__setattr__(self, "namespace", _freeze(self.namespace))


@dataclass(frozen=True)
class HelpHookContext:
    """Immutable help invocation state visible to help plugins."""

    backend: BackendName
    metadata: Mapping[str, Any]
    program: str
    terminal_width: int
    command_path: tuple[str, ...]
    schema: SchemaDescriptor

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze(self.metadata))
        object.__setattr__(self, "command_path", tuple(self.command_path))


@dataclass(frozen=True)
class ExecuteContext:
    """Immutable invocation state visible to execution wrappers."""

    backend: BackendName
    metadata: Mapping[str, Any]
    schema: SchemaDescriptor
    args: tuple[str, ...]
    namespace: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze(self.metadata))
        object.__setattr__(self, "args", tuple(self.args))
        object.__setattr__(self, "namespace", _freeze(self.namespace))


@dataclass(frozen=True)
class ParseFailureContext:
    """Immutable partial state visible during parse recovery."""

    backend: BackendName
    metadata: Mapping[str, Any]
    schema: SchemaDescriptor
    args: tuple[str, ...]
    namespace: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze(self.metadata))
        object.__setattr__(self, "args", tuple(self.args))
        object.__setattr__(self, "namespace", _freeze(self.namespace))


@dataclass(frozen=True)
class BackendPluginContext:
    """Explicit unstable access to a selected backend adapter and native parser."""

    backend: BackendName
    adapter: object = field(compare=False, repr=False)
    native_parser: object | None = field(default=None, compare=False, repr=False)


class ParseFailureKind(str, Enum):
    """Kinds of recoverable parse failures supported by the plugin system."""

    MISSING_ARGUMENTS = "missing_arguments"
    MISSING_SUBCOMMAND = "missing_subcommand"


@dataclass(frozen=True)
class ArgumentRef:
    """Stable reference to one schema argument inside a parsed command bucket."""

    command_path: tuple[str, ...]
    name: str
    argument: ArgumentDescriptor = field(compare=False, hash=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "command_path", tuple(self.command_path))


@dataclass(frozen=True)
class ParseFailure:
    """Backend-neutral structured recoverable parse failure."""

    kind: ParseFailureKind
    message: str
    command_path: tuple[str, ...]
    command_depth: int
    missing_arguments: tuple[ArgumentRef, ...] = ()
    available_subcommands: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "command_path", tuple(self.command_path))
        object.__setattr__(self, "missing_arguments", tuple(self.missing_arguments))
        object.__setattr__(
            self,
            "available_subcommands",
            tuple(self.available_subcommands),
        )


@dataclass(frozen=True)
class ProvideArgumentValues:
    """Recovery action that injects values into a partial parsed namespace."""

    values: Mapping[ArgumentRef, Any] = field(default_factory=dict)
    subcommands: Mapping[tuple[str, ...], str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        frozen_values: dict[ArgumentRef, Any] = {
            ref: _freeze(value) for ref, value in self.values.items()
        }
        frozen_subcommands: dict[tuple[str, ...], str] = {
            tuple(path): command for path, command in self.subcommands.items()
        }
        object.__setattr__(self, "values", MappingProxyType(frozen_values))
        object.__setattr__(self, "subcommands", MappingProxyType(frozen_subcommands))


@dataclass(frozen=True)
class AbortRecovery:
    """Recovery action that aborts the current CLI invocation."""

    exit_code: int = 2
    message: str | None = None


RecoveryAction: TypeAlias = ProvideArgumentValues | AbortRecovery


class InterfacyPlugin:
    """Base class for portable, backend-neutral Interfacy plugins."""

    name: str | None = None

    def configure(self, context: ConfigureContext) -> None:
        """Configure portable capabilities immediately after registration."""
        del context

    def before_parse(
        self,
        context: BeforeParseContext,
        args: tuple[str, ...],
    ) -> Sequence[str]:
        """Transform raw CLI arguments before backend parsing."""
        del context
        return args

    def after_parse(
        self,
        context: AfterParseContext,
        namespace: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Transform the parsed namespace before it is returned."""
        del context
        return namespace

    def transform_schema(
        self,
        context: SchemaTransformContext,
        schema: ParserSchema,
    ) -> ParserSchema:
        """Transform the explicit mutable schema payload."""
        del context
        return schema

    def transform_help(
        self,
        context: HelpHookContext,
        content: HelpContent,
    ) -> HelpContent:
        """Transform structured help content before final rendering."""
        del context
        return content

    def render_help(
        self,
        context: HelpHookContext,
        content: HelpContent,
    ) -> HelpResult | None:
        """Optionally provide final rendered help text."""
        del context, content
        return None

    def wrap_execute(
        self,
        context: ExecuteContext,
        call_next: Callable[[], Any],
    ) -> Any:
        """Wrap command execution."""
        del context
        return call_next()

    def recover_parse_failure(
        self,
        context: ParseFailureContext,
        failure: ParseFailure,
    ) -> RecoveryAction | None:
        """Optionally recover from a structured parse failure."""
        del context, failure
        return None

    @property
    def plugin_name(self) -> str:
        """Return the unique parser-local name used for plugin registration."""
        explicit_name = self.name
        if explicit_name:
            return explicit_name
        return type(self).__name__


class BackendPlugin(InterfacyPlugin):
    """Plugin opting into backend-specific, compatibility-limited adapter access."""

    backend: ClassVar[BackendName]

    def configure_backend(self, context: BackendPluginContext) -> None:
        """Configure against the selected backend's explicit native-access context."""
        del context


__all__ = [
    "AbortRecovery",
    "AfterParseContext",
    "ArgumentDescriptor",
    "ArgumentRef",
    "BackendName",
    "BackendPlugin",
    "BackendPluginContext",
    "BeforeParseContext",
    "ConfigureContext",
    "ExecuteContext",
    "HelpHookContext",
    "InterfacyPlugin",
    "ParseFailure",
    "ParseFailureContext",
    "ParseFailureKind",
    "ProvideArgumentValues",
    "RecoveryAction",
    "SchemaDescriptor",
    "SchemaTransformContext",
]

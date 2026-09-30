from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from typing import Any

from strto import StrToTypeParser

from interfacy.backends.base import BackendAdapter, BackendConfig, BackendSession, HelpPipeline
from interfacy.declarations.settings import BackendName, reserved_names_for_help_flags
from interfacy.declarations.sorting import HelpOptionSortRule, HelpSubcommandSortRule
from interfacy.engine.pipes import PipeState
from interfacy.engine.plugins import PluginManager
from interfacy.engine.settings import EngineSettings
from interfacy.help import HelpLayout
from interfacy.naming import AbbreviationGenerator, FlagStrategy
from interfacy.plugins import BackendPluginContext
from interfacy.schema.builder import SchemaBuildContext
from interfacy.schema.model import COMMAND_KEY, Command, ParserSchema


@dataclass(frozen=True, slots=True)
class CompiledGeneration:
    """Engine state that a compiled backend session was built from."""

    settings: tuple[Any, ...]
    registry: int
    metadata: Any
    plugins: int
    backend: str


@dataclass(frozen=True, slots=True)
class CompiledParser:
    """Backend session cached together with the schema and state it was compiled from."""

    generation: CompiledGeneration
    schema: ParserSchema
    schema_fingerprint: Any
    session: BackendSession[object]


def schema_build_context(
    settings: EngineSettings,
    *,
    commands: dict[str, Command],
    pipes: PipeState,
    metadata: Mapping[str, Any],
    type_parser: StrToTypeParser,
    flag_strategy: FlagStrategy,
    abbreviation_gen: AbbreviationGenerator,
    help_option_sort_effective: list[HelpOptionSortRule],
    help_subcommand_sort_effective: list[HelpSubcommandSortRule],
) -> SchemaBuildContext:
    """Collect the engine state the schema builder reads."""
    return SchemaBuildContext(
        pipe_target_resolver=pipes.resolve_by_names,
        description=settings.description,
        epilog=settings.epilog,
        commands=commands,
        command_key=COMMAND_KEY,
        reserved_flags=reserved_names_for_help_flags(settings.help_flags),
        method_skips=list(settings.method_skips or ()),
        allow_args_from_file=settings.allow_args_from_file,
        pipe_targets_default=pipes.default_targets,
        metadata=dict(metadata),
        executable_flags=list(settings.executable_flags or ()),
        type_parser=type_parser,
        flag_strategy=flag_strategy,
        abbreviation_gen=abbreviation_gen,
        include_inherited_methods=settings.include_inherited_methods,
        include_protected_methods=settings.include_protected_methods,
        include_private_methods=settings.include_private_methods,
        include_staticmethods=settings.include_staticmethods,
        include_classmethods=settings.include_classmethods,
        expand_model_params=settings.expand_model_params,
        model_expansion_max_depth=settings.model_expansion_max_depth,
        abbreviation_scope=settings.abbreviation_scope,
        help_option_sort=(
            list(settings.help_option_sort) if settings.help_option_sort is not None else None
        ),
        help_subcommand_sort=(
            list(settings.help_subcommand_sort)
            if settings.help_subcommand_sort is not None
            else None
        ),
        help_option_sort_effective=list(help_option_sort_effective),
        help_subcommand_sort_effective=list(help_subcommand_sort_effective),
        bool_negative_prefix=settings.bool_negative_prefix,
        help_flags=tuple(settings.help_flags),
    )


def backend_config(
    settings: EngineSettings,
    help_layout: HelpLayout,
    type_parser: StrToTypeParser,
) -> BackendConfig:
    """Collect the engine state a backend adapter compiles against."""
    return BackendConfig(
        help_flags=tuple(settings.help_flags),
        tab_completion=settings.tab_completion,
        allow_args_from_file=settings.allow_args_from_file,
        help_layout=help_layout,
        type_parser=type_parser,
    )


def generation_key(
    settings: EngineSettings,
    *,
    registry_generation: int,
    metadata: Mapping[str, Any],
    plugin_generation: int,
    backend: BackendName,
) -> CompiledGeneration:
    """Return the cache key for engine state that invalidates compiled sessions."""
    return CompiledGeneration(
        settings=tuple(fingerprint(value) for value in vars(settings).values()),
        registry=registry_generation,
        metadata=fingerprint(metadata),
        plugins=plugin_generation,
        backend=backend,
    )


def schema_fingerprint(value: Any, active: set[int] | None = None) -> Any:
    """Snapshot schema-owned structure without traversing or hashing user objects."""
    if type(value) in (str, int, float, bool, bytes, type(None)):
        return value

    framework_record = (
        not isinstance(value, type)
        and type(value).__module__.startswith("interfacy.")
        and is_dataclass(value)
    )
    if not framework_record and type(value) not in (dict, list, tuple, set, frozenset):
        return ("opaque", id(value))

    active = set() if active is None else active
    identity = id(value)
    if identity in active:
        return ("cycle", identity)

    active.add(identity)
    try:
        if framework_record:
            return type(value), tuple(
                (field.name, schema_fingerprint(getattr(value, field.name), active))
                for field in fields(value)
            )

        if type(value) is dict:
            return tuple(
                (schema_fingerprint(key, active), schema_fingerprint(item, active))
                for key, item in value.items()
            )

        items = tuple(schema_fingerprint(item, active) for item in value)

        return tuple(sorted(items, key=repr)) if type(value) in (set, frozenset) else items
    finally:
        active.remove(identity)


def fingerprint(value: Any) -> Any:
    """Return a hashable, order-stable snapshot of a settings or metadata value."""
    if isinstance(value, Mapping):
        return tuple(sorted((str(key), fingerprint(item)) for key, item in value.items()))

    if isinstance(value, (list, tuple)):
        return tuple(fingerprint(item) for item in value)

    if isinstance(value, (set, frozenset)):
        return tuple(sorted(repr(fingerprint(item)) for item in value))

    try:
        hash(value)
    except TypeError:
        return id(value)

    return value


class ParserCompiler:
    """Compile parser schemas into backend sessions and reuse the latest one."""

    def __init__(
        self,
        backend: BackendName,
        adapter: BackendAdapter[object],
        plugin_manager: PluginManager,
    ) -> None:
        self.backend: BackendName = backend
        self.adapter = adapter
        self.plugin_manager = plugin_manager
        self.compiled: CompiledParser | None = None

    @property
    def native_parser(self) -> Any | None:
        """Return the native parser of the cached session, if one is compiled."""
        return self.compiled.session.native_parser if self.compiled is not None else None

    def invalidate(self) -> None:
        """Drop the cached session so the next request recompiles."""
        self.compiled = None

    def session(
        self,
        schema: ParserSchema,
        generation: CompiledGeneration,
        help_pipeline: HelpPipeline,
        config: BackendConfig,
    ) -> BackendSession[object]:
        """
        Return a backend session for ``schema``, compiling it when the cache is stale.

        Freshly compiled sessions have backend plugins attached before they are cached.
        """
        fingerprint_value = schema_fingerprint(schema)
        compiled = self.compiled
        if (
            compiled is not None
            and compiled.generation == generation
            and compiled.schema == schema
            and compiled.schema_fingerprint == fingerprint_value
        ):
            return compiled.session

        session = self.adapter.compile(schema, help_pipeline, config)
        self.plugin_manager.attach_backend_plugins(
            BackendPluginContext(
                backend=self.backend,
                adapter=self.adapter,
                native_parser=session.native_parser,
            )
        )
        self.compiled = CompiledParser(generation, schema, fingerprint_value, session)

        return session


__all__ = [
    "CompiledGeneration",
    "CompiledParser",
    "ParserCompiler",
    "backend_config",
    "fingerprint",
    "generation_key",
    "schema_build_context",
    "schema_fingerprint",
]

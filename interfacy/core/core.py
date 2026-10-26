from __future__ import annotations

from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, TypeVar

from strto import StrToTypeParser

from interfacy.backends.base import BackendAdapter, BackendParseFailure, BackendSession
from interfacy.backends.registry import create_backend_adapter
from interfacy.common.debug import get_logger
from interfacy.common.resources import ParsedArguments, ResourceStack
from interfacy.common.sentinels import UnsetType
from interfacy.core.ancestor_options import (
    AncestorOptions,
    InterspersedOptionValueError,
    InvocationState,
)
from interfacy.core.commands import command_parameters, inspect_command_target
from interfacy.core.compiler import (
    ParserCompiler,
    backend_config,
    generation_key,
    schema_build_context,
)
from interfacy.core.diagnostics import render_diagnostic
from interfacy.core.help import (
    SchemaHelpPipeline,
    configure_help_layout,
    effective_option_sort,
    effective_subcommand_sort,
    render_help,
)
from interfacy.core.pipe_state import PipeState
from interfacy.core.plugins import PluginManager
from interfacy.core.recovery import recover_parse_failure, usage_presentation
from interfacy.core.registry import CommandRegistry
from interfacy.core.routing import select_commands
from interfacy.core.settings import CoreSettings, prepare_settings_update
from interfacy.core.snapshot import CoreSnapshot
from interfacy.declarations.executable_flags import ExecutableAction, executable_flag_tokens
from interfacy.declarations.groups import CommandGroup
from interfacy.declarations.options import DEFAULT_COMMAND_OPTIONS, CommandOptions
from interfacy.declarations.pipes import PipeTargets
from interfacy.declarations.settings import BackendName
from interfacy.declarations.sorting import HelpOptionSortRule, HelpSubcommandSortRule
from interfacy.exceptions import (
    CommandImportError,
    ConfigurationError,
    DuplicateCommandError,
    InterfacyExit,
    UsageError,
)
from interfacy.help import DiagnosticLayout, HelpLayout, StandardLayout
from interfacy.introspection.static_metadata import read_static_metadata
from interfacy.introspection.targets import ImportTarget
from interfacy.introspection.type_parsers import build_default_type_parser
from interfacy.naming import (
    AbbreviationGenerator,
    DefaultAbbreviationGenerator,
    DefaultFlagStrategy,
    FlagStrategy,
)
from interfacy.plugins import (
    AfterParseContext,
    BackendPlugin,
    BackendPluginContext,
    BeforeParseContext,
    ConfigureContext,
    ExecuteContext,
    InterfacyPlugin,
    SchemaDescriptor,
    SchemaTransformContext,
)
from interfacy.runtime.context import ExecutionContext
from interfacy.runtime.executable_flags import ExecutableActionPending, execute_executable_flag
from interfacy.runtime.invocation import (
    CommandTarget,
    InvocationInput,
    InvocationRuntime,
    resolve_args,
)
from interfacy.runtime.policy import RuntimePolicy
from interfacy.runtime.runner import SchemaRunner
from interfacy.schema.builder import ParserSchemaBuilder, SchemaBuildContext
from interfacy.schema.builder.groups import validate_group_names
from interfacy.schema.builder.settings import registered_command_options
from interfacy.schema.nodes import (
    COMMAND_KEY,
    Command,
    DeferredKind,
    DeferredTarget,
    ParserSchema,
)

logger = get_logger(__name__)
F = TypeVar("F", bound=Callable[..., Any])


@dataclass(frozen=True, slots=True)
class CoreComponents:
    """Collaborators derived from ``CoreSettings``; rebuilt together on every setup change."""

    help_layout: HelpLayout
    flag_strategy: FlagStrategy
    abbreviation_gen: AbbreviationGenerator
    type_parser: StrToTypeParser
    runtime_policy: RuntimePolicy


def derive_components(
    settings: CoreSettings,
    *,
    current_layout: HelpLayout,
    current_type_parser: StrToTypeParser | None,
    reset_fields: frozenset[str] = frozenset(),
) -> CoreComponents:
    """
    Build core collaborators from ``settings``.

    ``current_layout`` seeds the help layout when ``settings.help_layout`` is unset.
    ``current_type_parser`` is kept when ``settings.type_parser`` is unset; pass ``None`` to
    build a fresh default parser.
    """
    if settings.type_parser is not None:
        type_parser = settings.type_parser
    elif current_type_parser is not None:
        type_parser = current_type_parser
    else:
        type_parser = build_default_type_parser(from_file=settings.allow_args_from_file)

    return CoreComponents(
        help_layout=configure_help_layout(settings, current_layout, reset_fields),
        flag_strategy=settings.flag_strategy or DefaultFlagStrategy(),
        abbreviation_gen=settings.abbreviation_gen
        or DefaultAbbreviationGenerator(max_generated_len=settings.abbreviation_max_generated_len),
        type_parser=type_parser,
        runtime_policy=RuntimePolicy(
            display_result=settings.print_result,
            result_display_fn=settings.print_result_func,
            full_error_traceback=settings.full_error_traceback,
            on_interrupt=settings.on_interrupt,
            silent_interrupt=settings.silent_interrupt,
            logger_message_tag="interfacy",
        ),
    )


class InterfacyCore:
    COMMAND_KEY = COMMAND_KEY

    def __init__(
        self,
        settings: CoreSettings | None = None,
        *,
        backend: BackendName = "argparse",
        adapter: BackendAdapter[object] | None = None,
    ) -> None:
        self.adapter = adapter or create_backend_adapter(backend)
        if self.adapter.name != backend:
            raise ConfigurationError(
                f"Adapter backend '{self.adapter.name}' does not match selected backend '{backend}'"
            )

        self.backend: BackendName = backend
        self.metadata: dict[str, Any] = {}
        settings = settings or CoreSettings()
        components = derive_components(
            settings,
            current_layout=StandardLayout(),
            current_type_parser=None,
        )
        self.registry = CommandRegistry(components.flag_strategy.command_translator)
        default_pipes = (
            settings.pipe_targets if isinstance(settings.pipe_targets, PipeTargets) else None
        )
        self.pipes = PipeState(components.flag_strategy.command_translator, default_pipes)
        self.plugin_manager = PluginManager()
        self.compiler = ParserCompiler(backend, self.adapter, self.plugin_manager)
        self.last_schema: ParserSchema | None = None
        self._install(settings, components)

        for plugin in settings.plugins or ():
            self.add_plugin(plugin)

    def refresh_help_option_sort_rules(self) -> list[HelpOptionSortRule]:
        """Recompute and install effective option help ordering."""
        rules = effective_option_sort(self.settings.help_option_sort, self.help_layout)
        self.help_layout.help_option_sort_rules = rules
        self.compiler.invalidate()

        return list(rules)

    def refresh_help_subcommand_sort_rules(self) -> list[HelpSubcommandSortRule]:
        """Recompute and install effective subcommand help ordering."""
        rules = effective_subcommand_sort(self.settings.help_subcommand_sort, self.help_layout)
        self.help_layout.help_subcommand_sort_rules = rules
        self.compiler.invalidate()

        return list(rules)

    def add_plugin(self, plugin: InterfacyPlugin) -> InterfacyPlugin:
        registered = self.plugin_manager.add(
            plugin,
            ConfigureContext(
                backend=self.backend,
                metadata=self.metadata,
                register_type_parser=self.add_type_parser,
            ),
            BackendPluginContext(
                backend=self.backend,
                adapter=self.adapter,
                native_parser=self.compiler.native_parser,
            ),
        )
        self.compiler.invalidate()
        return registered

    def add_type_parser(
        self,
        typ: type[Any],
        parser: Callable[[str], Any],
    ) -> None:
        self.type_parser.add(typ, parser)
        self.compiler.invalidate()

    def apply_setup(self, **changes: Any) -> None:
        prepared = prepare_settings_update(self.settings, changes)
        if "flag_strategy" in prepared.changed_fields and self.registry.commands:
            raise ConfigurationError(
                "flag_strategy cannot be changed after commands have been registered"
            )

        components = derive_components(
            prepared.settings,
            current_layout=self.help_layout,
            current_type_parser=(
                None if "type_parser" in prepared.changed_fields else self.type_parser
            ),
            reset_fields=prepared.reset_fields,
        )
        additions = self.plugin_manager.validate_additions(
            prepared.plugin_additions,
            self.backend,
        )
        type_parser = components.type_parser
        staged_type_parser = deepcopy(type_parser) if additions else type_parser
        configure_context = ConfigureContext(
            backend=self.backend,
            metadata=self.metadata,
            register_type_parser=staged_type_parser.add,
        )
        backend_context = BackendPluginContext(
            backend=self.backend,
            adapter=self.adapter,
            native_parser=None,
        )
        for plugin in additions:
            plugin.configure(configure_context)
            if isinstance(plugin, BackendPlugin):
                plugin.configure_backend(backend_context)

        if additions:
            type_parser.parsers.clear()
            type_parser.parsers.update(staged_type_parser.parsers)

        self._install(prepared.settings, components)
        self.plugin_manager.commit_additions(additions)
        self.compiler.invalidate()

    def add_command(
        self,
        command: CommandTarget,
        name: str | None = None,
        description: str | None = None,
        aliases: Sequence[str] | None = None,
        pipe_targets: PipeTargets | dict[str, Any] | Sequence[str] | str | None = None,
        options: CommandOptions = DEFAULT_COMMAND_OPTIONS,
    ) -> Command:
        if isinstance(command, str):
            return self._add_deferred(
                ImportTarget.parse(command),
                "command",
                name=name,
                description=description,
                aliases=aliases,
                pipe_targets=pipe_targets,
                options=options,
            )

        if isinstance(command, CommandGroup):
            return self.add_group(
                command,
                name=name,
                description=description,
                aliases=aliases,
                options=options,
            )

        inspected = inspect_command_target(command, self.settings, options)

        with self._registration():
            canonical, registered_aliases = self.registry.register_name(
                default_name=inspected.name,
                explicit_name=name,
                aliases=aliases,
            )
            if canonical in self.registry.commands:
                raise DuplicateCommandError(canonical)

            raw_description = (
                description
                if description is not None
                else (inspected.description if inspected.has_docstring else None)
            )
            schema_command = Command(
                obj=inspected,
                canonical_name=canonical,
                cli_name=canonical,
                aliases=tuple(registered_aliases),
                raw_description=raw_description,
                help_group=options.help_group,
                executable_flags=list(options.executable_flags),
                overrides=options.overrides,
                params=dict(options.params),
            )
            self.registry.add(schema_command)
            if pipe_targets is not None:
                self.pipes.configure(pipe_targets, command=canonical)

            self.compiler.invalidate()

            return schema_command

    def command(self, **registration: Any) -> Callable[[F], F]:
        def decorator(target: F) -> F:
            self.add_command(target, **registration)
            return target

        return decorator

    def add_group(
        self,
        group: CommandGroup | str,
        name: str | None = None,
        description: str | None = None,
        aliases: Sequence[str] | None = None,
        options: CommandOptions = DEFAULT_COMMAND_OPTIONS,
    ) -> Command:
        if isinstance(group, str):
            return self._add_deferred(
                ImportTarget.parse(group),
                "group",
                name=name,
                description=description,
                aliases=aliases,
                pipe_targets=None,
                options=options,
            )

        combined_aliases: list[str] = list(aliases or ())
        combined_aliases.extend(alias for alias in group.aliases if alias not in combined_aliases)
        with self._registration():
            canonical, registered_aliases = self.registry.register_name(
                default_name=group.name,
                explicit_name=name,
                aliases=combined_aliases or None,
            )
            if canonical in self.registry.commands:
                raise DuplicateCommandError(canonical)

            command = self._group_command(group, canonical, options)
            if description is not None:
                command.raw_description = description

            command.aliases = tuple(registered_aliases)
            self.registry.add(command)
            self.compiler.invalidate()

            return command

    def build_parser_schema(self) -> ParserSchema:
        for canonical in list(self.registry.commands):
            self._resolve_deferred(canonical)

        return self._build_schema(None)

    def build_parser(self) -> Any:
        return self._session().native_parser

    def parse_args(self, args: Sequence[str] | None = None) -> ParsedArguments:
        try:
            invocation = self.parse(resolve_args(args))
            return ParsedArguments(invocation.namespace, invocation.resources)
        except ExecutableActionPending as e:
            raise InterfacyExit(
                execute_executable_flag(
                    e.action.flag,
                    display_result_fn=e.action.display_result_fn,
                )
            ) from None

    def parse(self, args: tuple[str, ...]) -> InvocationInput:
        with ResourceStack() as resources:
            state = InvocationState(
                args=args,
                ancestor_options=AncestorOptions(),
            )
            transformed_args = self.plugin_manager.before_parse(
                lambda current: BeforeParseContext(
                    backend=self.backend,
                    metadata=self.metadata,
                    args=current,
                ),
                args,
            )
            selected, schema = self._routed_schema(transformed_args)
            session = self._session(schema)
            normalized_args = tuple(state.ancestor_options.normalize_args(schema, transformed_args))
            outcome = session.parse(normalized_args)
            if isinstance(outcome, ExecutableAction):
                raise ExecutableActionPending(outcome)

            resources.callback(outcome.resources.close)
            supplied: dict[str, Any] | None = None
            if isinstance(outcome, BackendParseFailure):
                namespace, schema = recover_parse_failure(
                    session,
                    schema,
                    state,
                    outcome,
                    backend=self.backend,
                    metadata=self.metadata,
                    plugin_manager=self.plugin_manager,
                    max_attempts=self.settings.parse_recovery_max_attempts,
                    build_with_command=lambda canonical: self._build_selected(
                        selected | {canonical}
                    ),
                )
            else:
                namespace = dict(outcome.namespace)
                supplied = dict(outcome.supplied)

            try:
                ancestor_values = state.ancestor_options.resolve_values(
                    type_parser=self.type_parser
                )
                namespace = ancestor_values.apply_to(namespace)
            except InterspersedOptionValueError as e:
                session.present_error(
                    outcome.presentation
                    if isinstance(outcome, BackendParseFailure)
                    else usage_presentation(str(e), diagnostic=e.diagnostic)
                )

            if supplied is not None:
                supplied = ancestor_values.apply_to(supplied)
            namespace = self.plugin_manager.after_parse(
                lambda current: AfterParseContext(
                    backend=self.backend,
                    metadata=self.metadata,
                    schema=SchemaDescriptor.from_schema(schema),
                    args=normalized_args,
                    namespace=current,
                ),
                namespace,
            )

            return InvocationInput(
                normalized_args, namespace, schema, supplied, resources=resources.pop_all()
            )

    def invoke(
        self,
        *commands: CommandTarget,
        args: Sequence[str] | None = None,
    ) -> Any:
        with self._inline_commands(commands):
            return self._runtime.invoke(self._parse_step(commands, args), self.execute)

    async def invoke_async(
        self,
        *commands: CommandTarget,
        args: Sequence[str] | None = None,
    ) -> Any:
        with self._inline_commands(commands):
            return await self._runtime.invoke_async(
                self._parse_step(commands, args),
                self.execute_async,
            )

    def run(
        self,
        *commands: CommandTarget,
        args: Sequence[str] | None = None,
    ) -> Any:
        with self._inline_commands(commands):
            return self._runtime.run(self._parse_step(commands, args), self.execute)

    def execute(self, invocation: InvocationInput) -> Any:
        runner = SchemaRunner(
            invocation.namespace,
            self.execution_context(invocation.schema, invocation.supplied),
            list(invocation.args),
        )
        return self.plugin_manager.execute(self._execute_context(invocation), runner.run)

    def execute_async(self, invocation: InvocationInput) -> Any:
        runner = SchemaRunner(
            invocation.namespace,
            self.execution_context(invocation.schema, invocation.supplied),
            list(invocation.args),
        )
        return self.plugin_manager.execute(self._execute_context(invocation), runner.run_async)

    def execution_context(
        self,
        schema: ParserSchema,
        supplied: dict[str, Any] | None = None,
    ) -> ExecutionContext:
        return ExecutionContext(
            commands=schema.commands,
            argument_names=self.flag_strategy.argument_translator,
            command_names=self.flag_strategy.command_translator,
            type_parser=self.type_parser,
            schema=schema,
            read_piped_input=self.pipes.read_input,
            resolve_pipe_targets=lambda command, subcommand: self.pipes.resolve(
                command, subcommand=subcommand
            ),
            parameters_for=lambda command, subcommand: command_parameters(
                command,
                subcommand,
                self.flag_strategy.command_translator,
            ),
            supplied=supplied,
            command_key=self.COMMAND_KEY,
        )

    def pipe_to(self, *args: Any, **kwargs: Any) -> PipeTargets:
        result = self.pipes.configure(*args, **kwargs)
        self.compiler.invalidate()
        return result

    def snapshot(self) -> CoreSnapshot:
        return CoreSnapshot.capture(
            registry=self.registry,
            plugin_manager=self.plugin_manager,
            pipes=self.pipes,
            flag_strategy=self.flag_strategy,
            last_schema=self.last_schema,
            compiled=self.compiler.compiled,
        )

    def restore(self, snapshot: CoreSnapshot) -> None:
        snapshot.restore_components(
            registry=self.registry,
            plugin_manager=self.plugin_manager,
            pipes=self.pipes,
            flag_strategy=self.flag_strategy,
        )
        self.last_schema = snapshot.last_schema
        self.compiler.compiled = snapshot.compiled

    def render_help(
        self,
        schema: ParserSchema,
        command_path: tuple[str, ...],
        terminal_width: int | None = None,
        program: str | None = None,
    ) -> str:
        return render_help(
            schema,
            command_path,
            terminal_width,
            backend=self.backend,
            metadata=self.metadata,
            plugin_manager=self.plugin_manager,
            help_layout=self.help_layout,
            help_renderer=self.settings.help_renderer,
            program=program,
        )

    def render_diagnostic(self, failure: UsageError) -> str:
        schema = self.last_schema or self.build_parser_schema()
        return render_diagnostic(
            failure,
            schema,
            backend=self.backend,
            metadata=self.metadata,
            plugin_manager=self.plugin_manager,
            layout=self.settings.diagnostic_layout or DiagnosticLayout(),
            help_layout=self.help_layout,
            help_renderer=self.settings.help_renderer,
        )

    def _build_schema(self, selected: frozenset[str] | None) -> ParserSchema:
        builder = ParserSchemaBuilder(self._schema_build_context())
        schema = builder.build_unfinalized(selected)
        context = SchemaTransformContext(
            backend=self.backend,
            metadata=self.metadata,
        )
        schema = self.plugin_manager.transform_schema(context, schema)
        schema = builder.finalize(schema)
        self.last_schema = schema

        return schema

    def _add_deferred(
        self,
        target: ImportTarget,
        kind: DeferredKind,
        *,
        name: str | None,
        description: str | None,
        aliases: Sequence[str] | None,
        pipe_targets: PipeTargets | dict[str, Any] | Sequence[str] | str | None,
        options: CommandOptions,
    ) -> Command:
        metadata = read_static_metadata(target, group_factory=kind == "group")
        if not isinstance(metadata.name, UnsetType):
            default_name = metadata.name
        elif name is not None:
            default_name = name
        else:
            raise ConfigurationError(
                f"Cannot read the command name of '{target}' from its source; pass name="
            )

        if description is not None:
            raw_description: str | None = description
        elif not isinstance(metadata.description, UnsetType):
            raw_description = metadata.description
        else:
            raise ConfigurationError(
                f"Cannot read the description of '{target}' from its source; pass description="
            )

        combined_aliases: list[str] = list(aliases or ())
        combined_aliases.extend(a for a in metadata.aliases if a not in combined_aliases)
        with self._registration():
            canonical, registered_aliases = self.registry.register_name(
                default_name=default_name,
                explicit_name=name,
                aliases=combined_aliases or None,
            )
            if canonical in self.registry.commands:
                raise DuplicateCommandError(canonical)

            command = Command(
                obj=None,
                canonical_name=canonical,
                cli_name=canonical,
                aliases=tuple(registered_aliases),
                raw_description=raw_description,
                help_group=options.help_group,
                executable_flags=list(options.executable_flags),
                command_type="deferred",
                overrides=options.overrides,
                params=dict(options.params),
                deferred=DeferredTarget(target, "group" if metadata.is_group else kind),
            )
            self.registry.add(command)
            if pipe_targets is not None:
                self.pipes.configure(pipe_targets, command=canonical)

            self.compiler.invalidate()

            return command

    def _resolve_deferred(self, canonical: str) -> None:
        entry = self.registry.commands[canonical]
        deferred = entry.deferred
        if deferred is None:
            return

        try:
            target = deferred.target.load()
            if (
                deferred.kind == "group"
                and not isinstance(target, CommandGroup)
                and callable(target)
            ):
                target = target()
        except Exception as e:
            error = CommandImportError(canonical, str(deferred.target), e)
            raise error.with_traceback(e.__traceback__) from e

        options = registered_command_options(entry)
        if isinstance(target, CommandGroup):
            command = self._group_command(target, canonical, options)
            command.aliases = entry.aliases
            command.raw_description = entry.raw_description
        elif deferred.kind == "group":
            raise ConfigurationError(
                f"'{deferred.target}' must be a CommandGroup or a function that returns one"
            )
        else:
            command = Command(
                obj=inspect_command_target(target, self.settings, options),
                canonical_name=canonical,
                cli_name=canonical,
                aliases=entry.aliases,
                raw_description=entry.raw_description,
                help_group=options.help_group,
                executable_flags=list(options.executable_flags),
                overrides=options.overrides,
                params=dict(options.params),
            )

        self.registry.add(command)
        self.compiler.invalidate()

    def _group_command(
        self,
        group: CommandGroup,
        canonical: str,
        options: CommandOptions,
    ) -> Command:
        validate_group_names(group, self.flag_strategy.command_translator.compute)

        return Command(
            obj=None,
            canonical_name=canonical,
            cli_name=canonical,
            aliases=group.aliases,
            raw_description=group.description,
            help_group=options.help_group,
            executable_flags=list(options.executable_flags),
            command_type="group",
            is_leaf=False,
            group_source=group,
            overrides=options.overrides,
            params=dict(options.params),
        )

    def _routed_schema(self, args: tuple[str, ...]) -> tuple[frozenset[str], ParserSchema]:
        completion = self.adapter.completion_args() if self.settings.tab_completion else None
        routing_args = args if completion is None else completion
        from_file = self.settings.allow_args_from_file
        root_flags = set(self.settings.help_flags) | executable_flag_tokens(
            self.settings.executable_flags or ()
        )
        selected = select_commands(
            self.registry.commands,
            routing_args,
            allow_args_from_file=from_file,
            root_flags=root_flags,
        )
        schema = self._build_selected(selected)
        # Schema plugins can add names, so route again by the names the backend will see.
        reached = select_commands(
            schema.commands,
            routing_args,
            allow_args_from_file=from_file,
            root_flags=root_flags,
        )
        if reached <= selected:
            return selected, schema

        selected |= reached

        return selected, self._build_selected(selected)

    def _build_selected(self, selected: frozenset[str]) -> ParserSchema:
        for canonical in selected:
            self._resolve_deferred(canonical)

        return self._build_schema(selected)

    def _session(self, schema: ParserSchema | None = None) -> BackendSession[object]:
        current_schema = schema or self.build_parser_schema()
        session = self.compiler.session(
            current_schema,
            generation_key(
                self.settings,
                registry_generation=self.registry.generation,
                metadata=self.metadata,
                plugin_generation=self.plugin_manager.generation,
                backend=self.backend,
            ),
            SchemaHelpPipeline(self.render_help, current_schema),
            backend_config(self.settings, self.help_layout, self.type_parser),
        )
        self.last_schema = current_schema

        return session

    @contextmanager
    def _registration(self) -> Generator[None, None, None]:
        snapshot = self.snapshot()
        try:
            yield
        except BaseException:
            self.restore(snapshot)
            raise

    @contextmanager
    def _inline_commands(self, commands: Sequence[CommandTarget]) -> Generator[None, None, None]:
        """Scope commands passed to ``invoke``/``run`` to that single invocation."""
        if not commands:
            yield
            return

        snapshot = self.snapshot()
        try:
            yield
        finally:
            self.restore(snapshot)

    def _parse_step(
        self,
        commands: Sequence[CommandTarget],
        args: Sequence[str] | None,
    ) -> Callable[[], InvocationInput]:
        def parse() -> InvocationInput:
            self.pipes.reset_input()
            for command in commands:
                self.add_command(command)

            return self.parse(resolve_args(args))

        return parse

    def _install(self, settings: CoreSettings, components: CoreComponents) -> None:
        self.settings = settings
        self.help_layout = components.help_layout
        self.flag_strategy = components.flag_strategy
        self.abbreviation_gen = components.abbreviation_gen
        self.type_parser = components.type_parser
        self.runtime_policy = components.runtime_policy
        self.runtime_policy.diagnostic_renderer = self.render_diagnostic
        self._runtime = InvocationRuntime(components.runtime_policy)

    def _schema_build_context(self) -> SchemaBuildContext:
        return schema_build_context(
            self.settings,
            commands=self.registry.commands,
            pipes=self.pipes,
            metadata=self.metadata,
            type_parser=self.type_parser,
            flag_strategy=self.flag_strategy,
            abbreviation_gen=self.abbreviation_gen,
            help_option_sort_effective=list(self.help_layout.help_option_sort_rules),
            help_subcommand_sort_effective=list(self.help_layout.help_subcommand_sort_rules),
        )

    def _execute_context(self, invocation: InvocationInput) -> ExecuteContext:
        return ExecuteContext(
            backend=self.backend,
            metadata=self.metadata,
            schema=SchemaDescriptor.from_schema(invocation.schema),
            args=invocation.args,
            namespace=invocation.namespace,
        )


__all__ = ["CoreComponents", "InterfacyCore", "derive_components"]

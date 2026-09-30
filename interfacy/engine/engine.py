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
from interfacy.declarations.executable_flags import ExecutableAction
from interfacy.declarations.groups import CommandGroup
from interfacy.declarations.options import DEFAULT_COMMAND_OPTIONS, CommandOptions
from interfacy.declarations.pipes import PipeTargets
from interfacy.declarations.settings import BackendName
from interfacy.declarations.sorting import HelpOptionSortRule, HelpSubcommandSortRule
from interfacy.engine.commands import command_parameters, inspect_command_target
from interfacy.engine.compiler import (
    ParserCompiler,
    backend_config,
    generation_key,
    schema_build_context,
)
from interfacy.engine.help import (
    SchemaHelpPipeline,
    configure_help_layout,
    effective_option_sort,
    effective_subcommand_sort,
    render_help,
)
from interfacy.engine.parsing import (
    AncestorOptions,
    InterspersedOptionValueError,
    InvocationState,
)
from interfacy.engine.pipes import PipeState
from interfacy.engine.plugins import PluginManager
from interfacy.engine.recovery import recover_parse_failure, usage_presentation
from interfacy.engine.registry import CommandRegistry
from interfacy.engine.settings import EngineSettings, prepare_settings_update
from interfacy.engine.snapshot import EngineSnapshot
from interfacy.exceptions import ConfigurationError, DuplicateCommandError, InterfacyExit
from interfacy.help import HelpLayout, StandardLayout
from interfacy.introspection.parsers import build_default_type_parser
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
from interfacy.schema.model import COMMAND_KEY, Command, ParserSchema

logger = get_logger(__name__)
F = TypeVar("F", bound=Callable[..., Any])


@dataclass(frozen=True, slots=True)
class EngineComponents:
    """Collaborators derived from ``EngineSettings``; rebuilt together on every setup change."""

    help_layout: HelpLayout
    flag_strategy: FlagStrategy
    abbreviation_gen: AbbreviationGenerator
    type_parser: StrToTypeParser
    runtime_policy: RuntimePolicy


def derive_components(
    settings: EngineSettings,
    *,
    current_layout: HelpLayout,
    current_type_parser: StrToTypeParser | None,
    reset_fields: frozenset[str] = frozenset(),
) -> EngineComponents:
    """
    Build engine collaborators from ``settings``.

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

    return EngineComponents(
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


class InterfacyEngine:
    COMMAND_KEY = COMMAND_KEY

    def __init__(
        self,
        settings: EngineSettings | None = None,
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
        settings = settings or EngineSettings()
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
                parameter_settings=dict(options.parameter_settings),
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
        group: CommandGroup,
        name: str | None = None,
        description: str | None = None,
        aliases: Sequence[str] | None = None,
        options: CommandOptions = DEFAULT_COMMAND_OPTIONS,
    ) -> Command:
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

            command = ParserSchemaBuilder(self._schema_build_context()).build_from_group(
                group,
                canonical_name=canonical,
                options=options,
            )
            if description is not None:
                command.raw_description = description

            command.aliases = tuple(registered_aliases)
            command.group_source = group
            self.registry.add(command)
            self.compiler.invalidate()

            return command

    def build_parser_schema(self) -> ParserSchema:
        builder = ParserSchemaBuilder(self._schema_build_context())
        schema = builder.build_unfinalized()
        context = SchemaTransformContext(
            backend=self.backend,
            metadata=self.metadata,
        )
        schema = self.plugin_manager.transform_schema(context, schema)
        schema = builder.finalize(schema)
        self.last_schema = schema

        return schema

    def build_parser(self) -> Any:
        return self._session().native_parser

    def parse_args(self, args: Sequence[str] | None = None) -> dict[str, Any]:
        try:
            return self.parse(resolve_args(args)).namespace
        except ExecutableActionPending as e:
            raise InterfacyExit(
                execute_executable_flag(
                    e.action.flag,
                    display_result_fn=e.action.display_result_fn,
                )
            ) from None

    def parse(self, args: tuple[str, ...]) -> InvocationInput:
        state = InvocationState(
            args=args,
            ancestor_options=AncestorOptions(),
        )
        schema = self.build_parser_schema()
        session = self._session(schema)
        transformed_args = self.plugin_manager.before_parse(
            lambda current: BeforeParseContext(
                backend=self.backend,
                metadata=self.metadata,
                args=current,
            ),
            args,
        )
        normalized_args = tuple(state.ancestor_options.normalize_args(schema, transformed_args))
        outcome = session.parse(normalized_args)
        if isinstance(outcome, ExecutableAction):
            raise ExecutableActionPending(outcome)

        supplied: dict[str, Any] | None = None
        if isinstance(outcome, BackendParseFailure):
            namespace = recover_parse_failure(
                session,
                schema,
                state,
                outcome,
                backend=self.backend,
                metadata=self.metadata,
                plugin_manager=self.plugin_manager,
                max_attempts=self.settings.parse_recovery_max_attempts,
            )
        else:
            namespace = dict(outcome.namespace)
            supplied = dict(outcome.supplied)

        try:
            ancestor_values = state.ancestor_options.resolve_values()
            namespace = ancestor_values.apply_to(namespace)
        except InterspersedOptionValueError as e:
            session.present_error(
                outcome.presentation
                if isinstance(outcome, BackendParseFailure)
                else usage_presentation(str(e))
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

        return InvocationInput(normalized_args, namespace, schema, supplied)

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

    def snapshot(self) -> EngineSnapshot:
        return EngineSnapshot.capture(
            registry=self.registry,
            plugin_manager=self.plugin_manager,
            pipes=self.pipes,
            flag_strategy=self.flag_strategy,
            last_schema=self.last_schema,
            compiled=self.compiler.compiled,
        )

    def restore(self, snapshot: EngineSnapshot) -> None:
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
        )

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

    def _install(self, settings: EngineSettings, components: EngineComponents) -> None:
        self.settings = settings
        self.help_layout = components.help_layout
        self.flag_strategy = components.flag_strategy
        self.abbreviation_gen = components.abbreviation_gen
        self.type_parser = components.type_parser
        self.runtime_policy = components.runtime_policy
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


__all__ = ["EngineComponents", "InterfacyEngine", "derive_components"]

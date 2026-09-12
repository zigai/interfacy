from __future__ import annotations

import sys
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, fields, is_dataclass
from typing import Any, TypeVar

from objinspect import Class, Function, Method, Parameter, inspect

from interfacy.engine.backend import (
    BackendAdapter,
    BackendConfig,
    BackendParseFailure,
    BackendSession,
    HelpPipeline,
    ParseRequest,
    ParseResult,
    create_backend_adapter,
)
from interfacy.engine.parsing import (
    AncestorOptions,
    InterspersedOptionValueError,
    bucket_for_command_path,
)
from interfacy.engine.pipes import PipeState, PipeStateSnapshot
from interfacy.engine.plugins import PluginManager
from interfacy.engine.registry import CommandRegistry, NameRegistrySnapshot
from interfacy.engine.settings import (
    BackendName,
    EngineSettings,
    _EngineSettingsUpdate,
    _prepare_settings_update,
    reserved_names_for_help_flags,
    validate_abbreviation_scope,
    validate_help_option_sort,
    validate_help_subcommand_sort,
    validate_method_skips,
    validate_model_expansion_max_depth,
)
from interfacy.exceptions import ConfigurationError, DuplicateCommandError, InterfacyExit
from interfacy.executable_flag import (
    ExecutableAction,
    ExecutableActionPending,
    ExecutableFlag,
    execute_executable_flag,
    normalize_executable_flags,
)
from interfacy.group import CommandGroup
from interfacy.help.content import HelpContent, HelpContext, HelpRenderer, default_help_renderer
from interfacy.help.presets import StandardLayout
from interfacy.help.renderer import SchemaHelpRenderer
from interfacy.help.terminal import get_terminal_width
from interfacy.logger import get_logger
from interfacy.naming import DefaultAbbreviationGenerator, DefaultFlagStrategy
from interfacy.parameters import ParameterSettingsInput, normalize_parameter_settings
from interfacy.pipe import PipeTargets
from interfacy.plugins import (
    AbortRecovery,
    AfterParseContext,
    ArgumentDescriptor,
    ArgumentRef,
    BackendPlugin,
    BackendPluginContext,
    BeforeParseContext,
    ConfigureContext,
    ExecuteContext,
    HelpHookContext,
    InterfacyPlugin,
    ParseFailure,
    ParseFailureContext,
    ParseFailureKind,
    ProvideArgumentValues,
    SchemaDescriptor,
    SchemaTransformContext,
)
from interfacy.runner import SchemaRunner
from interfacy.runtime.context import ExecutionContext
from interfacy.runtime.invocation import (
    CommandTarget,
    InvocationInput,
    InvocationOperations,
    InvocationRuntime,
)
from interfacy.runtime.policy import RuntimePolicy
from interfacy.schema.builder import ParserSchemaBuilder, SchemaBuildContext
from interfacy.schema.schema import Argument, Command, ParserSchema, find_command
from interfacy.schema.sorting import (
    HelpOptionSortRule,
    HelpSubcommandSortRule,
    default_help_option_sort_rules,
    default_help_subcommand_sort_rules,
    resolve_help_option_sort_rules,
    resolve_help_subcommand_sort_rules,
)
from interfacy.schema.typing import resolve_objinspect_annotations
from interfacy.schema.validation import validate_help_group
from interfacy.type_parsers import build_default_type_parser

logger = get_logger(__name__)
F = TypeVar("F", bound=Callable[..., Any])


@dataclass(slots=True)
class InvocationState:
    args: tuple[str, ...]
    ancestor_options: AncestorOptions
    sequence: int
    recovery_attempts: int = 0


@dataclass(frozen=True, slots=True)
class _CompiledGeneration:
    settings: tuple[Any, ...]
    registry: int
    metadata: Any
    plugins: int
    backend: str


@dataclass(frozen=True, slots=True)
class _CompiledParser:
    generation: _CompiledGeneration
    schema: ParserSchema
    schema_fingerprint: Any
    session: BackendSession[object]


@dataclass(frozen=True, slots=True)
class _EngineSnapshot:
    registry_commands: dict[str, Command]
    registry_names: NameRegistrySnapshot
    registry_generation: int
    plugins: list[InterfacyPlugin]
    plugin_names: set[str]
    plugin_generation: int
    pipes: PipeStateSnapshot
    last_schema: ParserSchema | None
    compiled: _CompiledParser | None
    command_translations: dict[str, str]
    argument_translations: dict[str, str]


class _EngineHelpPipeline(HelpPipeline):
    def __init__(self, engine: InterfacyEngine, schema: ParserSchema) -> None:
        self._engine = engine
        self._schema = schema

    def render(
        self,
        command_path: tuple[str, ...],
        terminal_width: int | None = None,
    ) -> str:
        return self._engine.render_help(self._schema, command_path, terminal_width)


class InterfacyEngine(InvocationOperations):
    COMMAND_KEY = "command"

    def __init__(
        self,
        settings: EngineSettings | None = None,
        *,
        backend: BackendName = "argparse",
        adapter: BackendAdapter[object] | None = None,
    ) -> None:
        if backend not in ("argparse", "click"):
            raise ConfigurationError("backend must be one of: argparse, click")

        self.backend: BackendName = backend
        self.settings = settings or EngineSettings()
        self.metadata: dict[str, Any] = {}
        self.help_layout = (
            deepcopy(self.settings.help_layout) if self.settings.help_layout else StandardLayout()
        )
        if self.settings.help_colors is not None:
            self.help_layout.style = self.settings.help_colors

        if self.settings.help_position is not None:
            self.help_layout.help_position = self.settings.help_position

        self.flag_strategy = self.settings.flag_strategy or DefaultFlagStrategy()
        self.abbreviation_gen = self.settings.abbreviation_gen or DefaultAbbreviationGenerator(
            max_generated_len=self.settings.abbreviation_max_generated_len
        )
        self.type_parser = self.settings.type_parser or build_default_type_parser(
            from_file=self.settings.allow_args_from_file
        )
        self.help_option_sort_effective = self._resolve_option_sort()
        self.help_subcommand_sort_effective = self._resolve_subcommand_sort()
        self.help_layout.help_option_sort_rules = list(self.help_option_sort_effective)
        self.help_layout.help_subcommand_sort_rules = list(self.help_subcommand_sort_effective)
        self.registry = CommandRegistry(self.flag_strategy.command_translator)
        self.help_layout.name_registry = self.registry.names
        default_pipes = (
            self.settings.pipe_targets
            if isinstance(self.settings.pipe_targets, PipeTargets)
            else None
        )
        self.pipes = PipeState(self.flag_strategy.command_translator, default_pipes)
        self.plugin_manager = PluginManager()
        self.runtime_policy = RuntimePolicy(
            display_result=self.settings.print_result,
            result_display_fn=self.settings.print_result_func,
            full_error_traceback=self.settings.full_error_traceback,
            on_interrupt=self.settings.on_interrupt,
            silent_interrupt=self.settings.silent_interrupt,
            logger_message_tag="interfacy",
        )
        self.adapter = adapter or create_backend_adapter(backend)  # type: ignore[arg-type]
        if self.adapter.name != backend:
            raise ConfigurationError(
                f"Adapter backend '{self.adapter.name}' does not match selected backend '{backend}'"
            )

        self._last_schema: ParserSchema | None = None
        self._compiled: _CompiledParser | None = None
        self._runtime = InvocationRuntime(self, self.runtime_policy)
        self._invocation_sequence = 0

        for plugin in self.settings.plugins or ():
            self.add_plugin(plugin)

    @property
    def commands(self) -> dict[str, Command]:
        return self.registry.commands

    def refresh_help_option_sort_rules(self) -> list[HelpOptionSortRule]:
        """Recompute and install effective option help ordering."""
        self.help_option_sort_effective = self._resolve_option_sort()
        self.help_layout.help_option_sort_rules = list(self.help_option_sort_effective)
        self._invalidate_compiled()

        return list(self.help_option_sort_effective)

    def refresh_help_subcommand_sort_rules(self) -> list[HelpSubcommandSortRule]:
        """Recompute and install effective subcommand help ordering."""
        self.help_subcommand_sort_effective = self._resolve_subcommand_sort()
        self.help_layout.help_subcommand_sort_rules = list(self.help_subcommand_sort_effective)
        self._invalidate_compiled()

        return list(self.help_subcommand_sort_effective)

    def log(self, message: str) -> None:
        self.runtime_policy.log(message)

    def log_error(self, message: str) -> None:
        self.runtime_policy.log_error(message)

    def log_exception(self, e: BaseException) -> None:
        self.runtime_policy.log_exception(e)

    def log_interrupt(self) -> None:
        self.runtime_policy.log_interrupt()

    @property
    def plugins(self) -> list[InterfacyPlugin]:
        return self.plugin_manager.plugins

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
                native_parser=(
                    self._compiled.session.native_parser if self._compiled is not None else None
                ),
            ),
        )
        self._invalidate_compiled()
        return registered

    def add_type_parser(
        self,
        typ: type[Any],
        parser: Callable[[str], Any],
    ) -> None:
        self.type_parser.add(typ, parser)
        self._invalidate_compiled()

    def apply_setup(self, **values: Any) -> None:
        update = _EngineSettingsUpdate(**values)
        prepared = _prepare_settings_update(self.settings, update)
        if "flag_strategy" in prepared.changed_fields and self.commands:
            raise ConfigurationError(
                "flag_strategy cannot be changed after commands have been registered"
            )

        candidate = prepared.settings
        layout = (
            StandardLayout()
            if "help_layout" in prepared.reset_fields
            else deepcopy(candidate.help_layout)
            if candidate.help_layout is not None
            else deepcopy(self.help_layout)
        )
        if "help_colors" in prepared.reset_fields:
            layout.style = type(layout)().style
        elif candidate.help_colors is not None:
            layout.style = candidate.help_colors

        if candidate.help_position is not None:
            layout.help_position = candidate.help_position
        elif "help_position" in prepared.reset_fields:
            layout.help_position = None

        flag_strategy = candidate.flag_strategy or DefaultFlagStrategy()
        abbreviation_gen = candidate.abbreviation_gen or DefaultAbbreviationGenerator(
            max_generated_len=candidate.abbreviation_max_generated_len
        )
        if "type_parser" not in prepared.changed_fields and candidate.type_parser is None:
            type_parser = self.type_parser
        else:
            type_parser = candidate.type_parser or build_default_type_parser(
                from_file=candidate.allow_args_from_file
            )
        option_value = (
            list(candidate.help_option_sort)
            if candidate.help_option_sort is not None
            else layout.help_option_sort_default
        )
        option_rules = resolve_help_option_sort_rules(
            option_value,
            value_name="help_option_sort",
        )
        effective_options = list(option_rules) if option_rules else default_help_option_sort_rules()
        subcommand_value = (
            list(candidate.help_subcommand_sort)
            if candidate.help_subcommand_sort is not None
            else layout.help_subcommand_sort_default
        )
        subcommand_rules = resolve_help_subcommand_sort_rules(
            subcommand_value,
            value_name="help_subcommand_sort",
        )
        effective_subcommands = (
            list(subcommand_rules) if subcommand_rules else default_help_subcommand_sort_rules()
        )
        layout.help_option_sort_rules = list(effective_options)
        layout.help_subcommand_sort_rules = list(effective_subcommands)
        layout.name_registry = self.registry.names

        additions = self.plugin_manager.validate_additions(
            prepared.plugin_additions,
            self.backend,
        )
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

        runtime_policy = RuntimePolicy(
            display_result=candidate.print_result,
            result_display_fn=candidate.print_result_func,
            full_error_traceback=candidate.full_error_traceback,
            on_interrupt=candidate.on_interrupt,
            silent_interrupt=candidate.silent_interrupt,
            logger_message_tag=self.runtime_policy.logger_message_tag,
        )

        if additions:
            type_parser.parsers.clear()
            type_parser.parsers.update(staged_type_parser.parsers)

        self.settings = candidate
        self.help_layout = layout
        self.flag_strategy = flag_strategy
        self.abbreviation_gen = abbreviation_gen
        self.type_parser = type_parser
        self.help_option_sort_effective = effective_options
        self.help_subcommand_sort_effective = effective_subcommands
        self.runtime_policy = runtime_policy
        self._runtime = InvocationRuntime(self, runtime_policy)
        self.plugin_manager.commit_additions(additions)
        self._invalidate_compiled()

    def add_command(
        self,
        command: CommandTarget,
        name: str | None = None,
        description: str | None = None,
        aliases: Sequence[str] | None = None,
        pipe_targets: PipeTargets | dict[str, Any] | Sequence[str] | str | None = None,
        include_inherited_methods: bool | None = None,
        include_protected_methods: bool | None = None,
        include_private_methods: bool | None = None,
        include_staticmethods: bool | None = None,
        include_classmethods: bool | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: str | None = None,
        executable_flags: list[ExecutableFlag] | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
        method_skips: Sequence[str] | None = None,
        parameter_settings: ParameterSettingsInput | None = None,
    ) -> Command:
        help_group = validate_help_group(help_group)
        if isinstance(command, CommandGroup):
            return self.add_group(
                command,
                name=name,
                description=description,
                aliases=aliases,
                include_inherited_methods=include_inherited_methods,
                include_protected_methods=include_protected_methods,
                include_private_methods=include_private_methods,
                include_staticmethods=include_staticmethods,
                include_classmethods=include_classmethods,
                expand_model_params=expand_model_params,
                model_expansion_max_depth=model_expansion_max_depth,
                abbreviation_scope=abbreviation_scope,
                executable_flags=executable_flags,
                help_option_sort=help_option_sort,
                help_subcommand_sort=help_subcommand_sort,
                help_group=help_group,
                method_skips=method_skips,
                parameter_settings=parameter_settings,
            )

        inspected = inspect(
            command,
            init=True,
            public=True,
            inherited=self.settings.include_inherited_methods
            if include_inherited_methods is None
            else include_inherited_methods,
            static_methods=self.settings.include_staticmethods
            if include_staticmethods is None
            else include_staticmethods,
            classmethod=self.settings.include_classmethods
            if include_classmethods is None
            else include_classmethods,
            protected=self.settings.include_protected_methods
            if include_protected_methods is None
            else include_protected_methods,
            private=self.settings.include_private_methods
            if include_private_methods is None
            else include_private_methods,
        )
        resolve_objinspect_annotations(inspected)

        with self._registration():
            canonical, registered_aliases = self.registry.register_name(
                default_name=inspected.name,
                explicit_name=name,
                aliases=aliases,
            )
            if canonical in self.commands:
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
                parameters=[],
                initializer=[],
                subcommands=None,
                pipe_targets=None,
            )
            self._apply_command_settings(
                schema_command,
                include_inherited_methods=include_inherited_methods,
                include_protected_methods=include_protected_methods,
                include_private_methods=include_private_methods,
                include_staticmethods=include_staticmethods,
                include_classmethods=include_classmethods,
                expand_model_params=expand_model_params,
                model_expansion_max_depth=model_expansion_max_depth,
                abbreviation_scope=abbreviation_scope,
                executable_flags=executable_flags,
                help_option_sort=help_option_sort,
                help_subcommand_sort=help_subcommand_sort,
                help_group=help_group,
                method_skips=method_skips,
                parameter_settings=parameter_settings,
            )
            self.registry.add(schema_command)
            if pipe_targets is not None:
                self.pipes.configure(pipe_targets, command=canonical)

            self._invalidate_compiled()

            return schema_command

    def command(self, **options: Any) -> Callable[[F], F]:
        def decorator(target: F) -> F:
            self.add_command(target, **options)
            return target

        return decorator

    def add_group(
        self,
        group: CommandGroup,
        name: str | None = None,
        description: str | None = None,
        aliases: Sequence[str] | None = None,
        **options: Any,
    ) -> Command:
        options["help_group"] = validate_help_group(options.get("help_group"))
        combined_aliases: list[str] = list(aliases or ())
        combined_aliases.extend(alias for alias in group.aliases if alias not in combined_aliases)
        with self._registration():
            canonical, registered_aliases = self.registry.register_name(
                default_name=group.name,
                explicit_name=name,
                aliases=combined_aliases or None,
            )
            if canonical in self.commands:
                raise DuplicateCommandError(canonical)

            command = ParserSchemaBuilder(self._schema_build_context()).build_from_group(
                group,
                canonical_name=canonical,
                **self._group_build_options(options),
            )
            if description is not None:
                command.raw_description = description

            command.aliases = tuple(registered_aliases)
            command.group_source = group
            self._apply_command_settings(command, **options)
            self.registry.add(command)
            self._invalidate_compiled()

            return command

    def get_commands(self) -> list[Command]:
        return self.registry.all()

    def get_command_by_cli_name(self, cli_name: str) -> Command:
        return self.registry.get_by_cli_name(cli_name)

    def build_parser_schema(self) -> ParserSchema:
        builder = ParserSchemaBuilder(self._schema_build_context())
        schema = builder.build_unfinalized()
        context = SchemaTransformContext(
            backend=self.backend,
            metadata=self.metadata,
        )
        schema = self.plugin_manager.transform_schema(context, schema)
        schema = builder.finalize(schema)
        self._last_schema = schema

        return schema

    def build_parser(self) -> Any:
        return self._session().native_parser

    def get_last_schema(self) -> ParserSchema | None:
        return self._last_schema

    def parse_args(self, args: Sequence[str] | None = None) -> dict[str, Any]:
        resolved = tuple(sys.argv[1:] if args is None else args)
        try:
            return self.parse(resolved).namespace
        except ExecutableActionPending as e:
            raise InterfacyExit(
                execute_executable_flag(
                    e.action.flag,
                    display_result_fn=e.action.display_result_fn,
                )
            ) from None

    def parse(self, args: tuple[str, ...]) -> InvocationInput:
        self._invocation_sequence += 1
        state = InvocationState(
            args=args,
            ancestor_options=AncestorOptions(),
            sequence=self._invocation_sequence,
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
        outcome = session.parse(ParseRequest(normalized_args))
        if isinstance(outcome, ExecutableAction):
            raise ExecutableActionPending(outcome)

        if isinstance(outcome, BackendParseFailure):
            namespace = self._recover(session, schema, state, outcome)
        else:
            namespace = dict(outcome.namespace)

        try:
            ancestor_values = state.ancestor_options.resolve_values()
            namespace = ancestor_values.apply_to(schema, namespace)
        except InterspersedOptionValueError as e:
            session.present_error(
                outcome.presentation
                if isinstance(outcome, BackendParseFailure)
                else self._presentation(str(e))
            )

        if self.pipes.schema_uses_pipes(schema):
            source = session.parse(ParseRequest(normalized_args, default_policy="suppress"))
            source_namespace: dict[str, Any] | None = None
            if isinstance(source, ParseResult):
                source_namespace = ancestor_values.apply_to(schema, dict(source.namespace))
            self.pipes.record_cli_namespace(source_namespace)
        namespace = self.plugin_manager.after_parse(
            lambda current: AfterParseContext(
                backend=self.backend,
                metadata=self.metadata,
                schema=self._schema_descriptor(schema),
                args=normalized_args,
                namespace=current,
            ),
            namespace,
        )

        return InvocationInput(normalized_args, namespace)

    def invoke(
        self,
        *commands: CommandTarget,
        args: Sequence[str] | None = None,
    ) -> Any:
        return self._runtime.invoke(commands, args)

    async def invoke_async(
        self,
        *commands: CommandTarget,
        args: Sequence[str] | None = None,
    ) -> Any:
        return await self._runtime.invoke_async(commands, args)

    def run(
        self,
        *commands: CommandTarget,
        args: Sequence[str] | None = None,
    ) -> Any:
        return self._runtime.run(commands, args)

    def execute(self, invocation: InvocationInput) -> Any:
        runner = SchemaRunner(
            invocation.namespace,
            self.execution_context(),
            list(invocation.args),
        )
        context = ExecuteContext(
            backend=self.backend,
            metadata=self.metadata,
            schema=self._schema_descriptor(self._require_schema()),
            args=invocation.args,
            namespace=invocation.namespace,
        )
        return self.plugin_manager.execute(context, runner.run)

    def execute_async(self, invocation: InvocationInput) -> Any:
        runner = SchemaRunner(
            invocation.namespace,
            self.execution_context(),
            list(invocation.args),
        )
        context = ExecuteContext(
            backend=self.backend,
            metadata=self.metadata,
            schema=self._schema_descriptor(self._require_schema()),
            args=invocation.args,
            namespace=invocation.namespace,
        )
        return self.plugin_manager.execute(context, runner.run_async)

    def execution_context(self) -> ExecutionContext:
        return ExecutionContext(
            commands=self._last_schema.commands if self._last_schema is not None else self.commands,
            argument_names=self.flag_strategy.argument_translator,
            command_names=self.flag_strategy.command_translator,
            type_parser=self.type_parser,
            schema=self._last_schema,
            read_piped_input=self.pipes.read_input,
            resolve_pipe_targets=lambda command, subcommand: self.pipes.resolve(
                command, subcommand=subcommand
            ),
            parameters_for=self._parameters_for,
            cli_supplied_parameters_for=lambda command, subcommand: (
                self.pipes.cli_supplied_parameters(command, subcommand=subcommand)
            ),
            command_key=self.COMMAND_KEY,
        )

    def pipe_to(self, *args: Any, **kwargs: Any) -> PipeTargets:
        result = self.pipes.configure(*args, **kwargs)
        self._invalidate_compiled()
        return result

    def read_piped_input(self) -> str | None:
        return self.pipes.read_input()

    def reset_piped_input(self) -> None:
        self.pipes.reset_input()

    def reset_input(self) -> None:
        self.pipes.reset_input()

    def register_inline(self, commands: Sequence[CommandTarget]) -> None:
        for command in commands:
            self.add_command(command)

    def resolve_args(self, args: Sequence[str] | None) -> tuple[str, ...]:
        return tuple(sys.argv[1:] if args is None else args)

    def snapshot(self) -> _EngineSnapshot:
        commands, names, registry_generation = self.registry.snapshot()
        plugins, plugin_names, plugin_generation = self.plugin_manager.snapshot()
        return _EngineSnapshot(
            registry_commands=commands,
            registry_names=names,
            registry_generation=registry_generation,
            plugins=plugins,
            plugin_names=plugin_names,
            plugin_generation=plugin_generation,
            pipes=self.pipes.snapshot(),
            last_schema=self._last_schema,
            compiled=self._compiled,
            command_translations=dict(self.flag_strategy.command_translator.translations),
            argument_translations=dict(self.flag_strategy.argument_translator.translations),
        )

    def restore(self, snapshot: Any) -> None:
        if not isinstance(snapshot, _EngineSnapshot):
            raise TypeError("Invalid engine snapshot")

        self.registry.restore(
            snapshot.registry_commands,
            snapshot.registry_names,
            snapshot.registry_generation,
        )
        self.plugin_manager.restore(
            snapshot.plugins,
            snapshot.plugin_names,
            snapshot.plugin_generation,
        )
        self.pipes.restore(snapshot.pipes)
        self._last_schema = snapshot.last_schema
        self._compiled = snapshot.compiled
        self.flag_strategy.command_translator.translations.clear()
        self.flag_strategy.command_translator.translations.update(snapshot.command_translations)
        self.flag_strategy.argument_translator.translations.clear()
        self.flag_strategy.argument_translator.translations.update(snapshot.argument_translations)

    def render_help(
        self,
        schema: ParserSchema,
        command_path: tuple[str, ...],
        terminal_width: int | None = None,
    ) -> str:
        program = " ".join(command_path) or "main"
        semantic_path = command_path
        if not semantic_path and len(schema.commands) == 1 and not schema.is_multi_command:
            semantic_path = (next(iter(schema.commands.values())).canonical_name,)
        hook_context = HelpHookContext(
            backend=self.backend,
            metadata=self.metadata,
            program=program,
            terminal_width=terminal_width or get_terminal_width(),
            command_path=semantic_path,
            schema=self._schema_descriptor(schema),
        )

        def finalize(context: HelpContext, content: HelpContent) -> str:
            transformed = self.plugin_manager.transform_help(hook_context, content)
            plugin_result = self.plugin_manager.render_help(hook_context, transformed)
            if plugin_result is not None:
                return plugin_result.text

            configured_renderer: HelpRenderer | None = self.settings.help_renderer
            if configured_renderer is not None:
                return configured_renderer(context, transformed)

            return default_help_renderer(context, transformed)

        renderer = SchemaHelpRenderer(
            self.help_layout,
            terminal_width=hook_context.terminal_width,
            help_flags=schema.help_flags,
            final_renderer=finalize,
        )
        command = self._command_for_path(schema, command_path)
        if command is None:
            return renderer.render_parser_help(schema, program)

        return renderer.render_command_help(
            command,
            program,
            parser_schema=schema,
        )

    @staticmethod
    def _command_for_path(
        schema: ParserSchema,
        command_path: tuple[str, ...],
    ) -> Command | None:
        if not command_path:
            return None

        commands = schema.commands
        current: Command | None = None
        for segment in command_path:
            current = next(
                (
                    command
                    for command in commands.values()
                    if segment in (command.canonical_name, command.cli_name, *command.aliases)
                ),
                None,
            )
            if current is None:
                return None

            commands = current.subcommands or {}

        return current

    def _session(self, schema: ParserSchema | None = None) -> BackendSession[object]:
        current_schema = schema or self.build_parser_schema()
        generation = self._generation_key()
        schema_fingerprint = self._schema_fingerprint(current_schema)
        if (
            self._compiled is not None
            and self._compiled.generation == generation
            and self._compiled.schema == current_schema
            and self._compiled.schema_fingerprint == schema_fingerprint
        ):
            return self._compiled.session

        session = self.adapter.compile(
            current_schema,
            _EngineHelpPipeline(self, current_schema),
            self._backend_config(),
        )
        self.plugin_manager.attach_backend_plugins(
            BackendPluginContext(
                backend=self.backend,
                adapter=self.adapter,
                native_parser=session.native_parser,
            )
        )
        self._compiled = _CompiledParser(generation, current_schema, schema_fingerprint, session)
        self._last_schema = current_schema

        return session

    def _recover(
        self,
        session: BackendSession[object],
        schema: ParserSchema,
        state: InvocationState,
        initial: BackendParseFailure,
    ) -> dict[str, Any]:
        failure = initial
        namespace = dict(failure.partial_namespace)
        while state.recovery_attempts < self.settings.parse_recovery_max_attempts:
            state.recovery_attempts += 1
            descriptor = self._parse_failure(schema, namespace, failure.presentation.message)
            action = self.plugin_manager.recover(
                ParseFailureContext(
                    backend=self.backend,
                    metadata=self.metadata,
                    schema=self._schema_descriptor(schema),
                    args=state.args,
                    namespace=namespace,
                ),
                descriptor,
            )
            if action is None:
                break

            if isinstance(action, AbortRecovery):
                message = action.message or failure.presentation.message
                session.present_error(self._presentation(message, action.exit_code))

            self._apply_recovery_action(schema, namespace, descriptor, action)
            if not self._missing_required(schema, namespace):
                return namespace

        return session.present_error(failure.presentation)

    def _apply_recovery_action(
        self,
        schema: ParserSchema,
        namespace: dict[str, Any],
        failure: ParseFailure,
        action: ProvideArgumentValues,
    ) -> None:
        missing = set(failure.missing_arguments)
        for ref, value in action.values.items():
            if ref not in missing:
                raise ConfigurationError(
                    f"Recovery provided value for non-missing argument '{ref.name}'"
                )

            bucket = bucket_for_command_path(
                schema,
                namespace,
                ref.command_path,
                create=True,
            )
            if bucket is not None:
                bucket[ref.name] = value

        for path, command_name in action.subcommands.items():
            subcommands = self._subcommands_at_path(schema, path)
            selected = find_command(subcommands, command_name)
            if selected is None:
                raise ConfigurationError(f"Recovery selected invalid subcommand '{command_name}'")

            bucket = bucket_for_command_path(
                schema,
                namespace,
                path,
                create=True,
            )
            if bucket is not None:
                bucket[self.COMMAND_KEY] = selected.canonical_name
                bucket.setdefault(selected.canonical_name, {})

    @staticmethod
    def _subcommands_at_path(
        schema: ParserSchema,
        path: tuple[str, ...],
    ) -> dict[str, Command]:
        commands = schema.commands
        if not path:
            if len(commands) == 1 and not schema.is_multi_command:
                root = next(iter(commands.values()))
                if root.command_type != "group" and root.subcommands:
                    return root.subcommands

            return commands

        for segment in path:
            current = next(
                (
                    item
                    for item in commands.values()
                    if segment in (item.canonical_name, item.cli_name, *item.aliases)
                ),
                None,
            )
            if current is None:
                return {}

            commands = current.subcommands or {}

        return commands

    @classmethod
    def _available_subcommands(
        cls,
        schema: ParserSchema,
        path: tuple[str, ...],
    ) -> set[str]:
        return {
            name
            for item in cls._subcommands_at_path(schema, path).values()
            for name in (item.canonical_name, item.cli_name, *item.aliases)
        }

    def _parse_failure(
        self,
        schema: ParserSchema,
        namespace: dict[str, Any],
        message: str,
    ) -> ParseFailure:
        missing = tuple(self._missing_required(schema, namespace))
        kind = (
            ParseFailureKind.MISSING_ARGUMENTS if missing else ParseFailureKind.MISSING_SUBCOMMAND
        )
        return ParseFailure(
            kind=kind,
            message=message,
            command_path=missing[0].command_path if missing else (),
            command_depth=len(missing[0].command_path) if missing else 0,
            missing_arguments=missing,
            available_subcommands=tuple(sorted(self._available_subcommands(schema, ()))),
        )

    def _missing_required(
        self,
        schema: ParserSchema,
        namespace: dict[str, Any],
    ) -> list[ArgumentRef]:
        missing: list[ArgumentRef] = []
        single = len(schema.commands) == 1 and not schema.is_multi_command
        for command in schema.commands.values():
            path = () if single else (command.canonical_name,)
            bucket = namespace if single else namespace.get(command.canonical_name, {})
            if not isinstance(bucket, dict):
                bucket = {}
            missing.extend(
                ArgumentRef(path, argument.name, self._argument_descriptor(path, argument))
                for argument in (*command.initializer, *command.parameters)
                if argument.required and argument.name not in bucket
            )

        return missing

    @contextmanager
    def _registration(self) -> Generator[None, None, None]:
        snapshot = self.snapshot()
        try:
            yield
        except BaseException:
            self.restore(snapshot)
            raise

    def _schema_build_context(self) -> SchemaBuildContext:
        return SchemaBuildContext(
            pipe_target_resolver=self.pipes.resolve_by_names,
            description=self.settings.description,
            epilog=self.settings.epilog,
            commands=self.commands,
            command_key=self.COMMAND_KEY,
            reserved_flags=reserved_names_for_help_flags(self.settings.help_flags),
            method_skips=list(self.settings.method_skips or ()),
            allow_args_from_file=self.settings.allow_args_from_file,
            pipe_targets_default=self.pipes.default_targets,
            metadata=dict(self.metadata),
            executable_flags=list(self.settings.executable_flags or ()),
            type_parser=self.type_parser,
            flag_strategy=self.flag_strategy,
            abbreviation_gen=self.abbreviation_gen,
            include_inherited_methods=self.settings.include_inherited_methods,
            include_protected_methods=self.settings.include_protected_methods,
            include_private_methods=self.settings.include_private_methods,
            include_staticmethods=self.settings.include_staticmethods,
            include_classmethods=self.settings.include_classmethods,
            expand_model_params=self.settings.expand_model_params,
            model_expansion_max_depth=self.settings.model_expansion_max_depth,
            abbreviation_scope=self.settings.abbreviation_scope,
            help_option_sort=(
                list(self.settings.help_option_sort)
                if self.settings.help_option_sort is not None
                else None
            ),
            help_subcommand_sort=(
                list(self.settings.help_subcommand_sort)
                if self.settings.help_subcommand_sort is not None
                else None
            ),
            help_option_sort_effective=list(self.help_option_sort_effective),
            help_subcommand_sort_effective=list(self.help_subcommand_sort_effective),
            bool_negative_prefix=self.settings.bool_negative_prefix,
            help_flags=tuple(self.settings.help_flags),
        )

    def _backend_config(self) -> BackendConfig:
        return BackendConfig(
            help_flags=tuple(self.settings.help_flags),
            tab_completion=self.settings.tab_completion,
            allow_args_from_file=self.settings.allow_args_from_file,
            help_layout=self.help_layout,
            type_parser=self.type_parser,
        )

    def _generation_key(self) -> _CompiledGeneration:
        settings_key = tuple(self._fingerprint(value) for value in vars(self.settings).values())
        return _CompiledGeneration(
            settings=settings_key,
            registry=self.registry.generation,
            metadata=self._fingerprint(self.metadata),
            plugins=self.plugin_manager.generation,
            backend=self.backend,
        )

    @classmethod
    def _schema_fingerprint(cls, value: Any, active: set[int] | None = None) -> Any:
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
                    (field.name, cls._schema_fingerprint(getattr(value, field.name), active))
                    for field in fields(value)
                )

            if type(value) is dict:
                return tuple(
                    (cls._schema_fingerprint(key, active), cls._schema_fingerprint(item, active))
                    for key, item in value.items()
                )

            items = tuple(cls._schema_fingerprint(item, active) for item in value)

            return tuple(sorted(items, key=repr)) if type(value) in (set, frozenset) else items
        finally:
            active.remove(identity)

    @classmethod
    def _fingerprint(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            return tuple(sorted((str(key), cls._fingerprint(item)) for key, item in value.items()))

        if isinstance(value, (list, tuple)):
            return tuple(cls._fingerprint(item) for item in value)

        if isinstance(value, (set, frozenset)):
            return tuple(sorted(repr(cls._fingerprint(item)) for item in value))

        try:
            hash(value)
        except TypeError:
            return id(value)

        return value

    def _schema_descriptor(self, schema: ParserSchema) -> SchemaDescriptor:
        paths: list[tuple[str, ...]] = []
        arguments: list[ArgumentDescriptor] = []

        def visit(command: Command, path: tuple[str, ...]) -> None:
            paths.append(path)
            arguments.extend(
                self._argument_descriptor(path, argument)
                for argument in (*command.initializer, *command.parameters)
            )

            for child in (command.subcommands or {}).values():
                visit(child, (*path, child.canonical_name))

        for command in schema.commands.values():
            visit(command, (command.canonical_name,))

        return SchemaDescriptor(
            description=schema.description,
            epilog=schema.epilog,
            command_paths=tuple(paths),
            arguments=tuple(arguments),
            metadata=schema.metadata,
        )

    @staticmethod
    def _argument_descriptor(
        path: tuple[str, ...],
        argument: Argument,
    ) -> ArgumentDescriptor:
        return ArgumentDescriptor(
            command_path=path,
            name=argument.name,
            display_name=argument.display_name,
            kind=argument.kind.value,
            value_shape=argument.value_shape.value,
            flags=tuple(argument.flags),
            required=argument.required,
            type=argument.type,
            choices=tuple(argument.choices) if argument.choices else None,
            metadata=argument.metadata,
        )

    def _parameters_for(
        self,
        command: Command,
        subcommand: str | None,
    ) -> dict[str, Parameter]:
        obj = command.obj
        if isinstance(obj, (Function, Method)):
            return {parameter.name: parameter for parameter in obj.params}

        if not isinstance(obj, Class):
            return {}

        if subcommand in (None, "__init__"):
            method = obj.init_method
        else:
            method = next(
                (
                    item
                    for item in obj.methods
                    if item.name == subcommand
                    or self.flag_strategy.command_translator.translate(item.name) == subcommand
                ),
                None,
            )

        return {} if method is None else {parameter.name: parameter for parameter in method.params}

    def _apply_command_settings(self, command: Command, **options: Any) -> None:
        command.include_inherited_methods = options.get("include_inherited_methods")
        command.include_protected_methods = options.get("include_protected_methods")
        command.include_private_methods = options.get("include_private_methods")
        command.include_staticmethods = options.get("include_staticmethods")
        command.include_classmethods = options.get("include_classmethods")
        command.expand_model_params = options.get("expand_model_params")
        command.method_skips = (
            validate_method_skips(options["method_skips"])
            if options.get("method_skips") is not None
            else None
        )
        depth = options.get("model_expansion_max_depth")
        command.model_expansion_max_depth = (
            validate_model_expansion_max_depth(depth) if depth is not None else None
        )
        scope = options.get("abbreviation_scope")
        command.abbreviation_scope = validate_abbreviation_scope(scope) if scope else None
        command.executable_flags = normalize_executable_flags(options.get("executable_flags"))
        command.help_option_sort = (
            validate_help_option_sort(options["help_option_sort"])
            if options.get("help_option_sort") is not None
            else None
        )
        command.help_subcommand_sort = (
            validate_help_subcommand_sort(options["help_subcommand_sort"])
            if options.get("help_subcommand_sort") is not None
            else None
        )
        command.help_group = validate_help_group(options.get("help_group"))
        command.parameter_settings = normalize_parameter_settings(options.get("parameter_settings"))

    @staticmethod
    def _group_build_options(options: dict[str, Any]) -> dict[str, Any]:
        return {
            "include_inherited_methods": options.get("include_inherited_methods"),
            "include_protected_methods": options.get("include_protected_methods"),
            "include_private_methods": options.get("include_private_methods"),
            "include_staticmethods": options.get("include_staticmethods"),
            "include_classmethods": options.get("include_classmethods"),
            "expand_model_params": options.get("expand_model_params"),
            "method_skips": options.get("method_skips"),
            "model_expansion_max_depth": options.get("model_expansion_max_depth"),
            "abbreviation_scope": options.get("abbreviation_scope"),
            "executable_flags": options.get("executable_flags"),
            "help_option_sort": options.get("help_option_sort"),
            "help_subcommand_sort": options.get("help_subcommand_sort"),
            "help_group": options.get("help_group"),
            "parameter_settings": normalize_parameter_settings(options.get("parameter_settings")),
        }

    def _resolve_option_sort(self) -> list[HelpOptionSortRule]:
        value = (
            list(self.settings.help_option_sort)
            if self.settings.help_option_sort is not None
            else self.help_layout.help_option_sort_default
        )
        resolved = resolve_help_option_sort_rules(value, value_name="help_option_sort")
        return list(resolved) if resolved else default_help_option_sort_rules()

    def _resolve_subcommand_sort(self) -> list[HelpSubcommandSortRule]:
        value = (
            list(self.settings.help_subcommand_sort)
            if self.settings.help_subcommand_sort is not None
            else self.help_layout.help_subcommand_sort_default
        )
        resolved = resolve_help_subcommand_sort_rules(
            value,
            value_name="help_subcommand_sort",
        )
        return list(resolved) if resolved else default_help_subcommand_sort_rules()

    def _invalidate_compiled(self) -> None:
        self._compiled = None

    def _require_schema(self) -> ParserSchema:
        if self._last_schema is None:
            raise ConfigurationError("No schema is available for execution")

        return self._last_schema

    @staticmethod
    def _presentation(message: str, exit_code: int = 2) -> Any:
        from interfacy.engine.backend import NativePresentation

        return NativePresentation(kind="usage", message=message, exit_code=exit_code)


__all__ = ["InterfacyEngine", "InvocationState"]

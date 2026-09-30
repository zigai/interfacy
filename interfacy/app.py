from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, TypeVar

from strto import StrToTypeParser
from typing_extensions import final

from interfacy.common.sentinels import UNSET, UnsetType
from interfacy.declarations.executable_flags import ExecutableFlag
from interfacy.declarations.groups import CommandGroup
from interfacy.declarations.options import CommandOptions
from interfacy.declarations.params import ParameterSettingsInput
from interfacy.declarations.pipes import PipeTargets
from interfacy.declarations.settings import (
    DEFAULT_HELP_FLAGS,
    AbbreviationScope,
    BackendName,
    BooleanNegativePrefix,
    HelpFlags,
)
from interfacy.declarations.sorting import HelpOptionSortRule, HelpSubcommandSortRule
from interfacy.engine import InterfacyEngine
from interfacy.engine.settings import SETTING_NAMES, EngineSettings
from interfacy.help import HelpLayout
from interfacy.help.colors import InterfacyColors
from interfacy.help.content import HelpRenderer
from interfacy.naming import AbbreviationGenerator, FlagStrategy
from interfacy.plugins import InterfacyPlugin
from interfacy.runtime.invocation import CommandTarget, resolve_args
from interfacy.schema.model import Command, ParserSchema

Backend = BackendName
F = TypeVar("F", bound=Callable[..., object])


@final
class Interfacy:
    """
    Build and run command-line interfaces from Python callables.

    Register functions, classes, or command groups, and Interfacy turns their
    names, type annotations, and docstrings into commands, options, and help
    output. Use ``command()`` as a decorator, ``add_command()`` for explicit
    registration, or ``run()`` when you want to register and execute in one step.

    Args:
        description: Text shown before commands and options in help output.
        epilog: Text shown after generated help output.
        type_parser: Registry used to convert raw CLI strings into annotated types.
        help_layout: Layout configuration for generated help output.
        backend: Parser implementation to use. Must be ``"argparse"`` or ``"click"``.
        help_colors: Color theme applied by the help layout.
        print_result: Print returned command values after execution.
        tab_completion: Install shell completion support when the backend supports it.
        full_error_traceback: Include full tracebacks for runtime errors.
        allow_args_from_file: Enable ``@file`` argument expansion.
        sys_exit_enabled: Preserve the pre-0.8 embedded ``run()`` behavior when false.
        flag_strategy: Strategy for deriving option flags from Python names.
        abbreviation_gen: Generator used for short option flags.
        abbreviation_max_generated_len: Maximum generated short-flag length. Must be >= 1.
        abbreviation_scope: Scope where generated short flags may be reused.
        help_option_sort: Rules for ordering option help entries.
        help_subcommand_sort: Rules for ordering subcommand help entries.
        help_position: Absolute help-description column.
        executable_flags: Root-level flags that run without a command.
        pipe_targets: Default stdin routing configuration.
        print_result_func: Callable used when ``print_result`` is enabled.
        include_inherited_methods: Include inherited methods when registering classes.
        include_protected_methods: Include protected methods when registering classes.
        include_private_methods: Include private methods when registering classes.
        include_staticmethods: Include static methods when registering classes.
        include_classmethods: Include class methods when registering classes.
        on_interrupt: Callback invoked for handled `KeyboardInterrupt` instances.
        silent_interrupt: Suppress interrupt log output.
        expand_model_params: Expand supported model parameters into nested CLI flags.
        model_expansion_max_depth: Maximum model expansion depth. Must be >= 1.
        bool_negative_prefix: Prefix used for generated negative boolean flags.
        help_flags: Flag aliases that trigger help output.
        plugins: Plugins to register during initialization.
        method_skips: Class method names to skip when registering class commands.
        parse_recovery_max_attempts: Maximum plugin recovery attempts. Must be >= 0.
        ImportError: If ``backend="click"`` is requested without Click installed.
    """

    def __init__(
        self,
        description: str | None = None,
        epilog: str | None = None,
        type_parser: StrToTypeParser | None = None,
        help_layout: HelpLayout | None = None,
        *,
        backend: Backend = "argparse",
        help_colors: InterfacyColors | None = None,
        help_renderer: HelpRenderer | None = None,
        print_result: bool = False,
        tab_completion: bool = False,
        full_error_traceback: bool = False,
        allow_args_from_file: bool = True,
        sys_exit_enabled: bool = True,
        flag_strategy: FlagStrategy | None = None,
        abbreviation_gen: AbbreviationGenerator | None = None,
        abbreviation_max_generated_len: int = 1,
        abbreviation_scope: AbbreviationScope = "top_level_options",
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_position: int | None = None,
        executable_flags: Sequence[ExecutableFlag] | None = None,
        pipe_targets: PipeTargets | dict[str, object] | Sequence[object] | str | None = None,
        print_result_func: Callable[[object], object] = print,
        include_inherited_methods: bool = False,
        include_protected_methods: bool = False,
        include_private_methods: bool = False,
        include_staticmethods: bool = True,
        include_classmethods: bool = False,
        on_interrupt: Callable[[KeyboardInterrupt], None] | None = None,
        silent_interrupt: bool = True,
        expand_model_params: bool = True,
        model_expansion_max_depth: int = 3,
        bool_negative_prefix: BooleanNegativePrefix = "no-",
        help_flags: HelpFlags = DEFAULT_HELP_FLAGS,
        plugins: Sequence[InterfacyPlugin] | None = None,
        method_skips: Sequence[str] | None = None,
        parse_recovery_max_attempts: int = 3,
    ) -> None:
        # Every other parameter is an EngineSettings field of the same name;
        # tests/contracts/test_settings.py keeps the two in sync.
        settings = EngineSettings(
            **{name: value for name, value in locals().items() if name in SETTING_NAMES}
        )
        self._sys_exit_enabled = sys_exit_enabled
        self._engine = InterfacyEngine(settings, backend=backend)

    @property
    def backend(self) -> Backend:
        """Return the selected backend name."""
        return self._engine.backend

    @property
    def metadata(self) -> dict[str, Any]:
        """Return the engine metadata dictionary by identity."""
        return self._engine.metadata

    def add_plugin(self, plugin: InterfacyPlugin) -> InterfacyPlugin:
        """
        Register a plugin on the active backend parser.

        Raises:
            DuplicatePluginError: If another plugin with the same parser-local name exists.
        """
        return self._engine.add_plugin(plugin)

    def add_type_parser(
        self,
        typ: type[Any],
        parser: Callable[[str], Any],
    ) -> None:
        """
        Register a converter for an annotation type.

        The converter receives one raw CLI string and returns the value passed to
        the command callable.
        """
        self._engine.add_type_parser(typ, parser)

    @property
    def type_parser(self) -> StrToTypeParser:
        """Return the active type parser registry."""
        return self._engine.type_parser

    def apply_setup(
        self,
        *,
        help_layout: HelpLayout | UnsetType | None = UNSET,
        help_colors: InterfacyColors | UnsetType | None = UNSET,
        help_renderer: HelpRenderer | UnsetType | None = UNSET,
        type_parser: StrToTypeParser | UnsetType | None = UNSET,
        print_result: bool | UnsetType = UNSET,
        tab_completion: bool | UnsetType = UNSET,
        full_error_traceback: bool | UnsetType = UNSET,
        allow_args_from_file: bool | UnsetType = UNSET,
        flag_strategy: FlagStrategy | UnsetType | None = UNSET,
        abbreviation_gen: AbbreviationGenerator | UnsetType | None = UNSET,
        abbreviation_max_generated_len: int | UnsetType = UNSET,
        abbreviation_scope: AbbreviationScope | UnsetType = UNSET,
        help_option_sort: list[HelpOptionSortRule] | UnsetType | None = UNSET,
        help_subcommand_sort: list[HelpSubcommandSortRule] | UnsetType | None = UNSET,
        help_position: int | UnsetType | None = UNSET,
        executable_flags: Sequence[ExecutableFlag] | UnsetType | None = UNSET,
        include_inherited_methods: bool | UnsetType = UNSET,
        include_protected_methods: bool | UnsetType = UNSET,
        include_private_methods: bool | UnsetType = UNSET,
        include_staticmethods: bool | UnsetType = UNSET,
        include_classmethods: bool | UnsetType = UNSET,
        silent_interrupt: bool | UnsetType = UNSET,
        expand_model_params: bool | UnsetType = UNSET,
        model_expansion_max_depth: int | UnsetType = UNSET,
        bool_negative_prefix: BooleanNegativePrefix | UnsetType = UNSET,
        help_flags: HelpFlags | UnsetType | None = UNSET,
        plugins: Sequence[InterfacyPlugin] | UnsetType = UNSET,
        method_skips: Sequence[str] | UnsetType | None = UNSET,
        parse_recovery_max_attempts: int | UnsetType = UNSET,
    ) -> None:
        """
        Update parser defaults used by later registrations and parser builds.

        Omitted values retain their current setting. Explicit ``None`` resets only
        resettable settings. Plugins are additive and cannot be ``None``.

        Raises:
            ConfigurationError: If an update is invalid for the current parser state.
        """
        changes = {name: value for name, value in locals().items() if name != "self"}
        self._engine.apply_setup(**changes)

    def add_command(
        self,
        command: CommandTarget,
        name: str | None = None,
        description: str | None = None,
        aliases: Sequence[str] | None = None,
        pipe_targets: PipeTargets | dict[str, object] | Sequence[str] | str | None = None,
        include_inherited_methods: bool | None = None,
        include_protected_methods: bool | None = None,
        include_private_methods: bool | None = None,
        include_staticmethods: bool | None = None,
        include_classmethods: bool | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: AbbreviationScope | None = None,
        executable_flags: list[ExecutableFlag] | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
        method_skips: Sequence[str] | None = None,
        parameter_settings: ParameterSettingsInput | None = None,
    ) -> Command:
        """
        Register a function, class, instance, or command group.

        Per-command options override parser defaults for this command only. If
        ``name`` is omitted, the CLI name is derived from the command target.
        ``description``, ``aliases``, ``pipe_targets``, and ``help_group`` customize the
        public CLI surface without changing the underlying callable.

        Raises:
            DuplicateCommandError: If the command name or alias already exists.
            InvalidCommandError: If ``command`` cannot be converted to a CLI command.
            ConfigurationError: If an override is invalid.
        """
        # Every parameter after pipe_targets is a CommandOptions field of the same name;
        # tests/contracts/test_settings.py keeps the registration signatures in sync.
        return self._engine.add_command(
            command,
            name=name,
            description=description,
            aliases=aliases,
            pipe_targets=pipe_targets,
            options=CommandOptions.from_values(locals()),
        )

    def command(
        self,
        name: str | None = None,
        description: str | None = None,
        aliases: Sequence[str] | None = None,
        pipe_targets: PipeTargets | dict[str, object] | Sequence[str] | str | None = None,
        include_inherited_methods: bool | None = None,
        include_protected_methods: bool | None = None,
        include_private_methods: bool | None = None,
        include_staticmethods: bool | None = None,
        include_classmethods: bool | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: AbbreviationScope | None = None,
        executable_flags: list[ExecutableFlag] | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
        method_skips: Sequence[str] | None = None,
        parameter_settings: ParameterSettingsInput | None = None,
    ) -> Callable[[F], F]:
        """
        Return a decorator that registers a function or class as a command.

        Options passed to the decorator override parser defaults for the
        decorated target only. The decorated object is returned unchanged.
        """
        return self._engine.command(
            name=name,
            description=description,
            aliases=aliases,
            pipe_targets=pipe_targets,
            options=CommandOptions.from_values(locals()),
        )

    def add_group(
        self,
        group: CommandGroup,
        name: str | None = None,
        description: str | None = None,
        aliases: Sequence[str] | None = None,
        include_inherited_methods: bool | None = None,
        include_protected_methods: bool | None = None,
        include_private_methods: bool | None = None,
        include_staticmethods: bool | None = None,
        include_classmethods: bool | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: AbbreviationScope | None = None,
        executable_flags: list[ExecutableFlag] | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
        method_skips: Sequence[str] | None = None,
        parameter_settings: ParameterSettingsInput | None = None,
    ) -> Command:
        """
        Register an explicit command group.

        Group options override parser defaults for commands created from this
        group. If ``name`` is omitted, the CLI name is derived from the group.
        ``description``, ``aliases``, and ``help_group`` customize how the group is
        presented in generated help and command resolution.

        Raises:
            DuplicateCommandError: If the group name or alias already exists.
            ConfigurationError: If an override is invalid.
        """
        return self._engine.add_group(
            group,
            name=name,
            description=description,
            aliases=aliases,
            options=CommandOptions.from_values(locals()),
        )

    def get_commands(self) -> list[Command]:
        """Return registered command schemas in insertion order."""
        return self._engine.registry.all()

    def get_command_by_cli_name(self, cli_name: str) -> Command:
        """
        Resolve a registered command by CLI name or alias.

        Raises:
            InvalidCommandError: If `cli_name` does not resolve to a registered command.
        """
        return self._engine.registry.get_by_cli_name(cli_name)

    def get_args(self) -> list[str]:
        """Read the current process arguments excluding the executable name."""
        return list(resolve_args(None))

    def pipe_to(
        self,
        targets: PipeTargets | dict[str, object] | Sequence[str] | str,
        *,
        command: str | None = None,
        subcommand: str | None = None,
        **normalization_kwargs: Any,
    ) -> PipeTargets:
        """
        Configure stdin pipe routing for the parser or a command.

        Without ``command``, the targets become parser defaults. With ``command``
        and optionally ``subcommand``, they apply only to that command path.
        ``normalization_kwargs`` are passed through to pipe-target normalization.

        Raises:
            ConfigurationError: If the pipe target declaration is invalid.
        """
        return self._engine.pipe_to(
            targets,
            command=command,
            subcommand=subcommand,
            **normalization_kwargs,
        )

    def read_piped_input(self) -> str | None:
        """Read stdin data when available."""
        return self._engine.pipes.read_input()

    def reset_piped_input(self) -> None:
        """Clear cached stdin data."""
        self._engine.pipes.reset_input()

    def parse_args(self, args: list[str] | None = None) -> dict[str, object]:
        """
        Parse CLI arguments into a command argument mapping.

        If `args` is omitted, the current process arguments are used.
        """
        return self._engine.parse_args(args)

    def invoke(self, *commands: CommandTarget, args: list[str] | None = None) -> Any:
        """Invoke a command without rendering failures or terminating the process."""
        return self._engine.invoke(*commands, args=args)

    async def invoke_async(
        self,
        *commands: CommandTarget,
        args: list[str] | None = None,
    ) -> Any:
        """Invoke a command and await asynchronous execution without blocking a live loop."""
        return await self._engine.invoke_async(*commands, args=args)

    def run(self, *commands: CommandTarget, args: list[str] | None = None) -> Any:
        """Invoke a command and terminate unless embedded compatibility is enabled."""
        if not self._sys_exit_enabled:
            result = self._engine.invoke(*commands, args=args)
            if self._engine.runtime_policy.display_result:
                self._engine.runtime_policy.display(result)

            return result

        return self._engine.run(*commands, args=args)

    def build_parser(self) -> Any:
        """Build the backend parser for registered commands."""
        return self._engine.build_parser()

    def build_parser_schema(self) -> ParserSchema:
        """Build the parser schema for registered commands."""
        return self._engine.build_parser_schema()

    def get_last_schema(self) -> ParserSchema | None:
        """Return the most recently built parser schema, if any."""
        return self._engine.last_schema

    def refresh_help_option_sort_rules(self) -> list[HelpOptionSortRule]:
        """Recompute help option sort rules on the active backend parser."""
        return self._engine.refresh_help_option_sort_rules()

    def refresh_help_subcommand_sort_rules(self) -> list[HelpSubcommandSortRule]:
        """Recompute help subcommand sort rules on the active backend parser."""
        return self._engine.refresh_help_subcommand_sort_rules()

    def log(self, message: str) -> None:
        """Write an informational parser log message."""
        self._engine.runtime_policy.log(message)

    def log_error(self, message: str) -> None:
        """Write an error parser log message."""
        self._engine.runtime_policy.log_error(message)

    def log_exception(self, e: BaseException) -> None:
        """Write an exception parser log message."""
        self._engine.runtime_policy.log_exception(e)

    def log_interrupt(self) -> None:
        """Write the configured interrupt log message."""
        self._engine.runtime_policy.log_interrupt()


__all__ = ["Backend", "Interfacy"]

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any, Literal, TypeAlias, TypeVar

from objinspect import Class, Function
from strto import StrToTypeParser

from interfacy.appearance.help_sort import HelpOptionSortRule, HelpSubcommandSortRule
from interfacy.appearance.layout import HelpLayout, InterfacyColors
from interfacy.argparse_backend.argparser import Argparser
from interfacy.argparse_backend.argument_parser import ArgumentParser, NestedSubParsersAction
from interfacy.argparse_backend.help_formatter import InterfacyHelpFormatter
from interfacy.core import (
    DEFAULT_HELP_FLAGS,
    DEFAULT_NEGATIVE_BOOL_NAME_PREFIXES,
    AbbreviationScope,
    BooleanNegativePrefix,
    ExitCode,
    HelpFlags,
    InterfacyParser,
    NegativeBoolNameMode,
    NegativeBoolNamePrefixes,
)
from interfacy.exceptions import ConfigurationError
from interfacy.executable_flag import ExecutableFlag
from interfacy.group import CommandGroup
from interfacy.naming import AbbreviationGenerator, FlagStrategy
from interfacy.pipe import PipeTargets
from interfacy.plugins import InterfacyPlugin
from interfacy.schema.schema import Command, ParserSchema

if TYPE_CHECKING:
    import click

    BackendParser: TypeAlias = ArgumentParser | click.Command
else:
    BackendParser: TypeAlias = ArgumentParser | object

Backend = Literal["argparse", "click"]
CommandTarget = object
F = TypeVar("F", bound=Callable[..., object])


class Interfacy(InterfacyParser):
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
        run: Run backend setup immediately when supported by the selected backend.
        print_result: Print returned command values after execution.
        tab_completion: Install shell completion support when the backend supports it.
        full_error_traceback: Include full tracebacks for runtime errors.
        allow_args_from_file: Enable ``@file`` argument expansion.
        sys_exit_enabled: Call ``sys.exit`` for parser exits instead of returning codes.
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
        reraise_interrupt: Raise handled interrupts after logging or callbacks.
        expand_model_params: Expand supported model parameters into nested CLI flags.
        model_expansion_max_depth: Maximum model expansion depth. Must be >= 1.
        bool_negative_prefix: Prefix used for generated negative boolean flags.
        negative_bool_name_mode: Behavior for negative-looking bool names.
        negative_bool_name_prefixes: Prefixes treated as negative bool names.
        help_flags: Flag aliases that trigger help output.
        plugins: Plugins to register during initialization.
        method_skips: Class method names to skip when registering class commands.
        parse_recovery_max_attempts: Maximum plugin recovery attempts. Must be >= 0.
        formatter_class: Argparse help formatter class. Only valid with
            ``backend="argparse"``.

    Raises:
        ConfigurationError: If ``backend`` is unsupported or ``formatter_class`` is used with
            ``backend="click"``.
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
        run: bool = False,
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
        reraise_interrupt: bool = False,
        expand_model_params: bool = True,
        model_expansion_max_depth: int = 3,
        bool_negative_prefix: BooleanNegativePrefix = "no-",
        negative_bool_name_mode: NegativeBoolNameMode = "flag_only",
        negative_bool_name_prefixes: NegativeBoolNamePrefixes = DEFAULT_NEGATIVE_BOOL_NAME_PREFIXES,
        help_flags: HelpFlags = DEFAULT_HELP_FLAGS,
        plugins: Sequence[InterfacyPlugin] | None = None,
        method_skips: Sequence[str] | None = None,
        parse_recovery_max_attempts: int = 3,
        formatter_class: type[argparse.HelpFormatter] | None = None,
    ) -> None:
        self.backend: Backend = backend
        formatter = formatter_class or InterfacyHelpFormatter
        if backend == "argparse":
            self._parser: InterfacyParser = Argparser(
                description=description,
                epilog=epilog,
                type_parser=type_parser,
                help_layout=help_layout,
                help_colors=help_colors,
                run=run,
                print_result=print_result,
                tab_completion=tab_completion,
                full_error_traceback=full_error_traceback,
                allow_args_from_file=allow_args_from_file,
                sys_exit_enabled=sys_exit_enabled,
                flag_strategy=flag_strategy,
                abbreviation_gen=abbreviation_gen,
                abbreviation_max_generated_len=abbreviation_max_generated_len,
                abbreviation_scope=abbreviation_scope,
                help_option_sort=help_option_sort,
                help_subcommand_sort=help_subcommand_sort,
                help_position=help_position,
                executable_flags=executable_flags,
                pipe_targets=pipe_targets,
                print_result_func=print_result_func,
                include_inherited_methods=include_inherited_methods,
                include_protected_methods=include_protected_methods,
                include_private_methods=include_private_methods,
                include_staticmethods=include_staticmethods,
                include_classmethods=include_classmethods,
                on_interrupt=on_interrupt,
                silent_interrupt=silent_interrupt,
                reraise_interrupt=reraise_interrupt,
                expand_model_params=expand_model_params,
                model_expansion_max_depth=model_expansion_max_depth,
                bool_negative_prefix=bool_negative_prefix,
                negative_bool_name_mode=negative_bool_name_mode,
                negative_bool_name_prefixes=negative_bool_name_prefixes,
                help_flags=help_flags,
                plugins=plugins,
                method_skips=method_skips,
                parse_recovery_max_attempts=parse_recovery_max_attempts,
                formatter_class=formatter,
            )
            self.metadata = self._parser.metadata

            return

        if backend == "click":
            if formatter_class is not None:
                raise ConfigurationError(
                    "formatter_class is only supported with backend='argparse'"
                )

            try:
                from interfacy.click_backend import ClickParser
            except ImportError as exc:  # pragma: no cover - optional dependency guard
                raise ImportError(
                    "Click is required to use Interfacy with backend='click'. Install it with "
                    "\"pip install 'interfacy[click]'\" or \"uv add 'interfacy[click]'\"."
                ) from exc

            self._parser = ClickParser(
                description=description,
                epilog=epilog,
                type_parser=type_parser,
                help_layout=help_layout,
                help_colors=help_colors,
                run=run,
                print_result=print_result,
                tab_completion=tab_completion,
                full_error_traceback=full_error_traceback,
                allow_args_from_file=allow_args_from_file,
                sys_exit_enabled=sys_exit_enabled,
                flag_strategy=flag_strategy,
                abbreviation_gen=abbreviation_gen,
                abbreviation_max_generated_len=abbreviation_max_generated_len,
                abbreviation_scope=abbreviation_scope,
                help_option_sort=help_option_sort,
                help_subcommand_sort=help_subcommand_sort,
                help_position=help_position,
                executable_flags=executable_flags,
                pipe_targets=pipe_targets,
                print_result_func=print_result_func,
                include_inherited_methods=include_inherited_methods,
                include_protected_methods=include_protected_methods,
                include_private_methods=include_private_methods,
                include_staticmethods=include_staticmethods,
                include_classmethods=include_classmethods,
                on_interrupt=on_interrupt,
                silent_interrupt=silent_interrupt,
                reraise_interrupt=reraise_interrupt,
                expand_model_params=expand_model_params,
                model_expansion_max_depth=model_expansion_max_depth,
                bool_negative_prefix=bool_negative_prefix,
                negative_bool_name_mode=negative_bool_name_mode,
                negative_bool_name_prefixes=negative_bool_name_prefixes,
                help_flags=help_flags,
                plugins=plugins,
                method_skips=method_skips,
                parse_recovery_max_attempts=parse_recovery_max_attempts,
            )
            self.metadata = self._parser.metadata

            return

        raise ConfigurationError("backend must be one of: argparse, click")

    def add_plugin(self, plugin: InterfacyPlugin) -> InterfacyPlugin:
        """
        Register a plugin on the active backend parser.

        Raises:
            DuplicatePluginError: If another plugin with the same parser-local name exists.
        """
        return self._parser.add_plugin(plugin)

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
        self._parser.add_type_parser(typ, parser)

    @property
    def type_parser(self) -> StrToTypeParser:
        """Return the active type parser registry."""
        return self._parser.type_parser

    def apply_setup(
        self,
        *,
        help_layout: HelpLayout | None = None,
        help_colors: InterfacyColors | None = None,
        type_parser: StrToTypeParser | None = None,
        print_result: bool | None = None,
        tab_completion: bool | None = None,
        full_error_traceback: bool | None = None,
        allow_args_from_file: bool | None = None,
        flag_strategy: FlagStrategy | None = None,
        abbreviation_gen: AbbreviationGenerator | None = None,
        abbreviation_max_generated_len: int | None = None,
        abbreviation_scope: AbbreviationScope | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_position: int | None = None,
        include_inherited_methods: bool | None = None,
        include_protected_methods: bool | None = None,
        include_private_methods: bool | None = None,
        include_staticmethods: bool | None = None,
        include_classmethods: bool | None = None,
        silent_interrupt: bool | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        bool_negative_prefix: BooleanNegativePrefix | None = None,
        negative_bool_name_mode: NegativeBoolNameMode | None = None,
        negative_bool_name_prefixes: NegativeBoolNamePrefixes | None = None,
        help_flags: HelpFlags | None = None,
        plugins: Sequence[InterfacyPlugin] | None = None,
        method_skips: Sequence[str] | None = None,
        parse_recovery_max_attempts: int | None = None,
    ) -> None:
        """
        Update parser defaults used by later registrations and parser builds.

        Arguments left as ``None`` keep their current value. Plugins supplied here
        are registered immediately.

        Raises:
            ConfigurationError: If an update is invalid for the current parser state.
        """
        self._parser.apply_setup(
            help_layout=help_layout,
            help_colors=help_colors,
            type_parser=type_parser,
            print_result=print_result,
            tab_completion=tab_completion,
            full_error_traceback=full_error_traceback,
            allow_args_from_file=allow_args_from_file,
            flag_strategy=flag_strategy,
            abbreviation_gen=abbreviation_gen,
            abbreviation_max_generated_len=abbreviation_max_generated_len,
            abbreviation_scope=abbreviation_scope,
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
            help_position=help_position,
            include_inherited_methods=include_inherited_methods,
            include_protected_methods=include_protected_methods,
            include_private_methods=include_private_methods,
            include_staticmethods=include_staticmethods,
            include_classmethods=include_classmethods,
            silent_interrupt=silent_interrupt,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=model_expansion_max_depth,
            bool_negative_prefix=bool_negative_prefix,
            negative_bool_name_mode=negative_bool_name_mode,
            negative_bool_name_prefixes=negative_bool_name_prefixes,
            help_flags=help_flags,
            plugins=plugins,
            method_skips=method_skips,
            parse_recovery_max_attempts=parse_recovery_max_attempts,
        )

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
        return self._parser.add_command(
            command=command,
            name=name,
            description=description,
            aliases=aliases,
            pipe_targets=pipe_targets,
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
    ) -> Callable[[F], F]:
        """
        Return a decorator that registers a function or class as a command.

        Options passed to the decorator override parser defaults for the
        decorated target only. The decorated object is returned unchanged.
        """
        return self._parser.command(
            name=name,
            description=description,
            aliases=aliases,
            pipe_targets=pipe_targets,
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
        return self._parser.add_group(
            group=group,
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
        )

    def get_commands(self) -> list[Command]:
        """Return registered command schemas in insertion order."""
        return self._parser.get_commands()

    def get_command_by_cli_name(self, cli_name: str) -> Command:
        """
        Resolve a registered command by CLI name or alias.

        Raises:
            InvalidCommandError: If `cli_name` does not resolve to a registered command.
        """
        return self._parser.get_command_by_cli_name(cli_name)

    def get_args(self) -> list[str]:
        """Read the current process arguments excluding the executable name."""
        return self._parser.get_args()

    def exit(self, code: ExitCode) -> ExitCode:
        """Exit the process or return ``code``, depending on parser settings."""
        return self._parser.exit(code)

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
        return self._parser.pipe_to(
            targets,
            command=command,
            subcommand=subcommand,
            **normalization_kwargs,
        )

    def read_piped_input(self) -> str | None:
        """Read stdin data when available."""
        return self._parser.read_piped_input()

    def reset_piped_input(self) -> None:
        """Clear cached stdin data."""
        self._parser.reset_piped_input()

    def parser_from_command(self, command: Function | Class, main: bool = False) -> BackendParser:
        """
        Build a backend parser from an inspected command.

        ``main`` tells the backend to build the command as the root parser rather
        than as a nested command parser.

        Raises:
            InvalidCommandError: If ``command`` is not a supported inspected object.
        """
        return self._parser.parser_from_command(command, main=main)

    def parse_args(self, args: list[str] | None = None) -> dict[str, object]:
        """
        Parse CLI arguments into a command argument mapping.

        If `args` is omitted, the current process arguments are used.
        """
        return self._parser.parse_args(args)

    def run(self, *commands: CommandTarget, args: list[str] | None = None) -> Any:
        """
        Register any command targets, parse arguments, and execute the selection.

        Returns the command result unless execution exits through the configured
        backend. If `args` is omitted, the current process arguments are used.
        """
        return self._parser.run(*commands, args=args)

    def parser_from_function(
        self,
        function: Function,
        parser: ArgumentParser | None = None,
        taken_flags: list[str] | None = None,
    ) -> BackendParser:
        """
        Build a backend parser for an inspected function.

        Existing parser and flag reservations are used by backends that build
        nested or shared argparse parsers.
        """
        return self._parser.parser_from_function(
            function,
            parser=parser,
            taken_flags=taken_flags,
        )

    def parser_from_class(
        self,
        cls: Class,
        parser: ArgumentParser | None = None,
        subparser: NestedSubParsersAction | None = None,
    ) -> BackendParser:
        """
        Build a backend parser for an inspected class.

        Existing parser objects are used by backends that populate nested
        argparse parser trees.
        """
        return self._parser.parser_from_class(cls, parser=parser, subparser=subparser)

    def parser_from_multiple_commands(self, *commands: CommandTarget) -> BackendParser:
        """Build a backend parser from multiple command targets."""
        return self._parser.parser_from_multiple_commands(*commands)

    def install_tab_completion(self, parser: BackendParser) -> None:
        """Install tab completion for a backend parser when supported."""
        self._parser.install_tab_completion(parser)

    def build_parser(self) -> BackendParser:
        """Build the backend parser for registered commands."""
        return self._parser.build_parser()

    def build_parser_schema(self) -> ParserSchema:
        """Build the parser schema for registered commands."""
        return self._parser.build_parser_schema()

    def get_last_schema(self) -> ParserSchema | None:
        """Return the most recently built parser schema, if any."""
        return self._parser.get_last_schema()

    def log(self, message: str) -> None:
        """Write an informational parser log message."""
        self._parser.log(message)

    def log_error(self, message: str) -> None:
        """Write an error parser log message."""
        self._parser.log_error(message)

    def log_exception(self, e: BaseException) -> None:
        """Write an exception parser log message."""
        self._parser.log_exception(e)

    def log_interrupt(self) -> None:
        """Write the configured interrupt log message."""
        self._parser.log_interrupt()


__all__ = ["Backend", "Interfacy"]

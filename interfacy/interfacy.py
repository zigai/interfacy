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
from interfacy.core import AbbreviationScope, BooleanNegativePrefix, ExitCode, InterfacyParser
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
    High-level Interfacy parser.

    Args:
        backend: Parser backend to use. Defaults to ``"argparse"``. Use
            ``"click"`` for the Click-backed parser.
        formatter_class: Argparse formatter class. Only valid with
            ``backend="argparse"``.
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
        include_classmethods: bool = False,
        on_interrupt: Callable[[KeyboardInterrupt], None] | None = None,
        silent_interrupt: bool = True,
        reraise_interrupt: bool = False,
        expand_model_params: bool = True,
        model_expansion_max_depth: int = 3,
        bool_negative_prefix: BooleanNegativePrefix = "no-",
        plugins: Sequence[InterfacyPlugin] | None = None,
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
                include_classmethods=include_classmethods,
                on_interrupt=on_interrupt,
                silent_interrupt=silent_interrupt,
                reraise_interrupt=reraise_interrupt,
                expand_model_params=expand_model_params,
                model_expansion_max_depth=model_expansion_max_depth,
                bool_negative_prefix=bool_negative_prefix,
                plugins=plugins,
                formatter_class=formatter,
            )

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
                include_classmethods=include_classmethods,
                on_interrupt=on_interrupt,
                silent_interrupt=silent_interrupt,
                reraise_interrupt=reraise_interrupt,
                expand_model_params=expand_model_params,
                model_expansion_max_depth=model_expansion_max_depth,
                bool_negative_prefix=bool_negative_prefix,
                plugins=plugins,
            )

            return

        raise ConfigurationError("backend must be one of: argparse, click")

    def add_plugin(self, plugin: InterfacyPlugin) -> InterfacyPlugin:
        return self._parser.add_plugin(plugin)

    def add_type_parser(
        self,
        typ: type[Any],
        parser: Callable[[str], Any],
    ) -> None:
        self._parser.add_type_parser(typ, parser)

    @property
    def type_parser(self) -> StrToTypeParser:
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
        include_classmethods: bool | None = None,
        silent_interrupt: bool | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        bool_negative_prefix: BooleanNegativePrefix | None = None,
        plugins: Sequence[InterfacyPlugin] | None = None,
    ) -> None:
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
            include_classmethods=include_classmethods,
            silent_interrupt=silent_interrupt,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=model_expansion_max_depth,
            bool_negative_prefix=bool_negative_prefix,
            plugins=plugins,
        )

    def add_command(
        self,
        command: CommandTarget,
        name: str | None = None,
        description: str | None = None,
        aliases: Sequence[str] | None = None,
        pipe_targets: PipeTargets | dict[str, object] | Sequence[str] | str | None = None,
        include_inherited_methods: bool | None = None,
        include_classmethods: bool | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: AbbreviationScope | None = None,
        executable_flags: list[ExecutableFlag] | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
    ) -> Command:
        return self._parser.add_command(
            command=command,
            name=name,
            description=description,
            aliases=aliases,
            pipe_targets=pipe_targets,
            include_inherited_methods=include_inherited_methods,
            include_classmethods=include_classmethods,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=model_expansion_max_depth,
            abbreviation_scope=abbreviation_scope,
            executable_flags=executable_flags,
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
            help_group=help_group,
        )

    def command(
        self,
        name: str | None = None,
        description: str | None = None,
        aliases: Sequence[str] | None = None,
        pipe_targets: PipeTargets | dict[str, object] | Sequence[str] | str | None = None,
        include_inherited_methods: bool | None = None,
        include_classmethods: bool | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: AbbreviationScope | None = None,
        executable_flags: list[ExecutableFlag] | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
    ) -> Callable[[F], F]:
        return self._parser.command(
            name=name,
            description=description,
            aliases=aliases,
            pipe_targets=pipe_targets,
            include_inherited_methods=include_inherited_methods,
            include_classmethods=include_classmethods,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=model_expansion_max_depth,
            abbreviation_scope=abbreviation_scope,
            executable_flags=executable_flags,
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
            help_group=help_group,
        )

    def add_group(
        self,
        group: CommandGroup,
        name: str | None = None,
        description: str | None = None,
        aliases: Sequence[str] | None = None,
        include_inherited_methods: bool | None = None,
        include_classmethods: bool | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: AbbreviationScope | None = None,
        executable_flags: list[ExecutableFlag] | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
    ) -> Command:
        return self._parser.add_group(
            group=group,
            name=name,
            description=description,
            aliases=aliases,
            include_inherited_methods=include_inherited_methods,
            include_classmethods=include_classmethods,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=model_expansion_max_depth,
            abbreviation_scope=abbreviation_scope,
            executable_flags=executable_flags,
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
            help_group=help_group,
        )

    def get_commands(self) -> list[Command]:
        return self._parser.get_commands()

    def get_command_by_cli_name(self, cli_name: str) -> Command:
        return self._parser.get_command_by_cli_name(cli_name)

    def get_args(self) -> list[str]:
        return self._parser.get_args()

    def exit(self, code: ExitCode) -> ExitCode:
        return self._parser.exit(code)

    def pipe_to(
        self,
        targets: PipeTargets | dict[str, object] | Sequence[str] | str,
        *,
        command: str | None = None,
        subcommand: str | None = None,
        **normalization_kwargs: Any,
    ) -> PipeTargets:
        return self._parser.pipe_to(
            targets,
            command=command,
            subcommand=subcommand,
            **normalization_kwargs,
        )

    def read_piped_input(self) -> str | None:
        return self._parser.read_piped_input()

    def reset_piped_input(self) -> None:
        self._parser.reset_piped_input()

    def parser_from_command(self, command: Function | Class, main: bool = False) -> BackendParser:
        return self._parser.parser_from_command(command, main=main)

    def parse_args(self, args: list[str] | None = None) -> dict[str, object]:
        return self._parser.parse_args(args)

    def run(self, *commands: CommandTarget, args: list[str] | None = None) -> Any:
        return self._parser.run(*commands, args=args)

    def parser_from_function(
        self,
        function: Function,
        parser: ArgumentParser | None = None,
        taken_flags: list[str] | None = None,
    ) -> BackendParser:
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
        return self._parser.parser_from_class(cls, parser=parser, subparser=subparser)

    def parser_from_multiple_commands(self, *commands: CommandTarget) -> BackendParser:
        return self._parser.parser_from_multiple_commands(*commands)

    def install_tab_completion(self, parser: BackendParser) -> None:
        self._parser.install_tab_completion(parser)

    def build_parser(self) -> BackendParser:
        return self._parser.build_parser()

    def build_parser_schema(self) -> ParserSchema:
        return self._parser.build_parser_schema()

    def get_last_schema(self) -> ParserSchema | None:
        return self._parser.get_last_schema()

    def log(self, message: str) -> None:
        self._parser.log(message)

    def log_error(self, message: str) -> None:
        self._parser.log_error(message)

    def log_exception(self, e: BaseException) -> None:
        self._parser.log_exception(e)

    def log_interrupt(self) -> None:
        self._parser.log_interrupt()


__all__ = ["Backend", "Interfacy"]

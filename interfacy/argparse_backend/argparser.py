import argparse
import sys
from collections.abc import Callable
from typing import Any, ClassVar

from objinspect import Class, Function, Method, Parameter
from objinspect.typing import type_args, type_origin
from strto import StrToTypeParser

from interfacy.argparse_backend.argument_parser import ArgumentParser, namespace_to_dict
from interfacy.argparse_backend.help_formatter import InterfacyHelpFormatter
from interfacy.argparse_backend.runner import ArgparseRunner
from interfacy.command import Command
from interfacy.core import ExitCode, InterfacyParser
from interfacy.exceptions import (
    ConfigurationError,
    DuplicateCommandError,
    InterfacyError,
    InvalidCommandError,
    ReservedFlagError,
    UnsupportedParameterTypeError,
)
from interfacy.logger import get_logger
from interfacy.naming import AbbreviationGenerator, FlagStrategy
from interfacy.themes import ParserTheme

logger = get_logger(__name__)


class Argparser(InterfacyParser):
    RESERVED_FLAGS: ClassVar[list[str]] = ["h", "help"]
    COMMAND_KEY = "command"

    def __init__(
        self,
        description: str | None = None,
        epilog: str | None = None,
        type_parser: StrToTypeParser | None = None,
        theme: ParserTheme | None = None,
        *,
        run: bool = False,
        print_result: bool = False,
        tab_completion: bool = False,
        full_error_traceback: bool = False,
        allow_args_from_file: bool = True,
        sys_exit_enabled: bool = True,
        flag_strategy: FlagStrategy | None = None,
        abbreviation_gen: AbbreviationGenerator | None = None,
        pipe_target: dict[str, str] | None = None,
        print_result_func: Callable = print,
        formatter_class=InterfacyHelpFormatter,
    ) -> None:
        super().__init__(
            description,
            epilog,
            theme,
            type_parser,
            run=run,
            allow_args_from_file=allow_args_from_file,
            flag_strategy=flag_strategy,
            abbreviation_gen=abbreviation_gen,
            pipe_target=pipe_target,
            tab_completion=tab_completion,
            print_result=print_result,
            print_result_func=print_result_func,
            full_error_traceback=full_error_traceback,
            sys_exit_enabled=sys_exit_enabled,
        )
        self.formatter_class = formatter_class
        self._parser = None
        del self.type_parser.parsers[list]

    def _new_parser(self, name: str | None = None):
        return ArgumentParser(name, formatter_class=self.formatter_class)

    def _add_parameter_to_parser(
        self,
        param: Parameter,
        parser: ArgumentParser,
        taken_flags: list[str],
    ):
        if param.name in taken_flags:
            raise ReservedFlagError(param.name)
        name = self.flag_strategy.argument_translator.translate(param.name)
        flags = self.flag_strategy.get_arg_flags(name, param, taken_flags, self.abbreviation_gen)
        extra_args = self._extra_add_arg_params(param, flags)
        logger.info(f"Flags: {flags}, Extra args: {extra_args}")
        return parser.add_argument(*flags, **extra_args)

    def parser_from_function(
        self,
        function: Function,
        parser: ArgumentParser | None = None,
        taken_flags: list[str] | None = None,
    ) -> ArgumentParser:
        """Create an ArgumentParser from a Function"""
        taken_flags = [] if taken_flags is None else taken_flags
        parser = parser or self._new_parser()

        if function.has_docstring:
            parser.description = self.theme.format_description(function.description)

        for param in function.params:
            self._add_parameter_to_parser(param=param, parser=parser, taken_flags=taken_flags)

        return parser

    def parser_from_method(
        self,
        method: Method,
        taken_flags: list[str],
        parser: ArgumentParser | None = None,
    ) -> ArgumentParser:
        """Create an ArgumentParser from a Method"""
        parser = parser or self._new_parser()

        is_initialized = hasattr(method.func, "__self__")
        if (init := Class(method.cls).init_method) and not is_initialized:
            for param in init.params:
                self._add_parameter_to_parser(param=param, parser=parser, taken_flags=taken_flags)

        for param in method.params:
            self._add_parameter_to_parser(param=param, parser=parser, taken_flags=taken_flags)

        if method.has_docstring:
            parser.description = self.theme.format_description(method.description)

        return parser

    def parser_from_class(
        self,
        cls: Class,
        parser: ArgumentParser | None = None,
        subparser=None,
    ) -> ArgumentParser:
        """Create an ArgumentParser from a Class"""
        parser = parser or self._new_parser()

        if cls.has_docstring:
            parser.description = self.theme.format_description(cls.description)
        parser.epilog = self.theme.get_help_for_class(cls)  # type: ignore

        if cls.has_init and not cls.is_initialized:
            for param in cls.get_method("__init__").params:
                self._add_parameter_to_parser(
                    parser=parser,
                    param=param,
                    taken_flags=[*self.RESERVED_FLAGS, self.COMMAND_KEY],
                )

        if subparser is None:
            subparser = parser.add_subparsers(dest=self.COMMAND_KEY, required=True)

        for method in cls.methods:
            if method.name in self.method_skips:
                continue
            taken_flags = [*self.RESERVED_FLAGS]
            method_name = self.flag_strategy.command_translator.translate(method.name)
            sp = subparser.add_parser(method_name, description=method.description)
            self.parser_from_function(function=method, parser=sp, taken_flags=taken_flags)

        return parser

    def parser_from_command(
        self,
        command: Command,
        parser: ArgumentParser | None = None,
        subparser=None,
    ):
        obj = command.obj
        if isinstance(obj, Method):
            return self.parser_from_method(
                obj,
                taken_flags=[*self.RESERVED_FLAGS],
                parser=parser,
            )
        if isinstance(obj, Function):
            return self.parser_from_function(
                obj,
                taken_flags=[*self.RESERVED_FLAGS],
                parser=parser,
            )
        if isinstance(obj, Class):
            return self.parser_from_class(obj, parser=parser, subparser=subparser)
        raise InvalidCommandError(obj)

    def parser_from_multiple_commands(
        self,
        commands: dict[str, Command],
        parser: ArgumentParser | None = None,
    ) -> ArgumentParser:
        logger.debug(f"Building parser from {len(commands)} commands")
        parser = parser or self._new_parser()
        parser.epilog = self.theme.get_help_for_multiple_commands(commands)
        subparsers = parser.add_subparsers(dest=self.COMMAND_KEY, required=True)

        for canonical_name, cmd in commands.items():
            sp = subparsers.add_parser(
                canonical_name,
                description=cmd.description,
                aliases=list(cmd.aliases),
            )
            obj = cmd.obj
            if isinstance(obj, Function):
                self.parser_from_function(
                    function=obj, taken_flags=[*self.RESERVED_FLAGS], parser=sp
                )
            elif isinstance(obj, Class):
                self.parser_from_class(obj, sp)
            elif isinstance(obj, Method):
                self.parser_from_method(obj, taken_flags=[*self.RESERVED_FLAGS], parser=sp)
            else:
                raise InvalidCommandError(obj)
        return parser

    def _extra_add_arg_params(self, param: Parameter, flags: tuple[str, ...]) -> dict[str, Any]:
        """
        This method creates a dictionary with additional argument parameters needed to
        customize argparse's `add_argument` method based on a given `Parameter` object.

        Args:
            param (Parameter): The parameter for which to construct additional parameters.
            flags (tuple[str, ...]): The flags to be used for the argument.

        Returns:
            dict[str, Any]: A dictionary containing additional parameter settings like "help",
            "required", "metavar", and "default".

        """
        extra: dict[str, Any] = {}
        extra["help"] = self.theme.get_help_for_parameter(param)

        if param.is_typed:
            t_origin = type_origin(param.type)
            is_list_alias = t_origin is list

            if is_list_alias or param.type is list:
                extra["nargs"] = "*"

            if is_list_alias:
                t_args = type_args(param.type)
                assert t_args
                extra["type"] = self.type_parser.get_parse_func(t_args[0])
            else:
                extra["type"] = self.type_parser.get_parse_func(param.type)

        if self.theme.clear_metavar:
            if not param.is_required:
                extra["metavar"] = "\b"

        if self.flag_strategy.style == "required_positional":
            is_positional = all([not i.startswith("-") for i in flags])
            logger.debug(f"Flags: {flags}, positional={is_positional}")
            if not is_positional:
                extra["required"] = param.is_required

        # Handle boolean parameters
        if param.is_typed and param.type is bool:
            extra["action"] = argparse.BooleanOptionalAction
            if not param.is_required:
                extra["default"] = param.default
            else:
                extra["default"] = False
            return extra

        # Add default value
        if not param.is_required:
            extra["default"] = param.default
        return extra

    def install_tab_completion(self, parser: ArgumentParser) -> None:
        """
        Install tab completion for the given parser.
        Requires the argcomplete package to be installed.

        'pip install argcomplete'
        """
        try:
            import argcomplete

        except ImportError:
            print(
                "argcomplete not installed. Tab completion not available."
                " Install with 'pip install argcomplete'",
                file=sys.stderr,
            )
            return

        argcomplete.autocomplete(parser)

    def build_parser(self) -> ArgumentParser:
        if not self.commands:
            raise ConfigurationError("No commands were provided")

        commands = self.get_commands()
        if len(commands) == 1:
            parser = self.parser_from_command(commands.pop())
        else:
            parser = self.parser_from_multiple_commands(self.commands)

        if self.description:
            parser.description = self.theme.format_description(self.description)

        if self.enable_tab_completion:
            self.install_tab_completion(parser)
        return parser

    def parse_args(self, args: list[str] | None = None) -> dict[str, Any]:
        args = args if args is not None else self.get_args()
        parser = self.build_parser()
        self._parser = parser
        parsed = parser.parse_args(args)
        namespace = namespace_to_dict(parsed)

        if self.COMMAND_KEY in namespace:
            cli_name = namespace[self.COMMAND_KEY]
            canonical = self.name_registry.canonical_for(cli_name) or cli_name
            namespace[self.COMMAND_KEY] = canonical
            command_args_key = canonical if canonical in namespace else cli_name
            if command_args_key not in namespace:
                raise InvalidCommandError(cli_name)
            if command_args_key != canonical:
                namespace[canonical] = namespace.pop(command_args_key)

        return namespace

    def run(self, *commands: Callable | type | object, args: list[str] | None = None) -> Any:
        try:
            for cmd in commands:
                self.add_command(cmd, name=None, description=None)

            args = args if args is not None else self.get_args()
            logger.info(f"Got args: {args}")
            namespace = self.parse_args(args)
        except (
            DuplicateCommandError,
            UnsupportedParameterTypeError,
            ReservedFlagError,
            InvalidCommandError,
            ConfigurationError,
        ) as e:
            self.log_exception(e)
            self.exit(ExitCode.ERR_PARSING)
            return e

        try:
            runner = ArgparseRunner(
                namespace=namespace,
                args=args,
                parser=self._parser,
                builder=self,
            )
            result = runner.run()
        except InterfacyError as e:
            self.log_exception(e)
            self.exit(ExitCode.ERR_RUNTIME_INTERNAL)
            return e

        except Exception as e:
            self.log_exception(e)
            self.exit(ExitCode.ERR_RUNTIME)
            return e

        if self.display_result:
            self.result_display_fn(result)

        self.exit(ExitCode.SUCCESS)
        return result

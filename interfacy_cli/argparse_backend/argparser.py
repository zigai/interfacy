import argparse
import sys
from argparse import ArgumentParser
from typing import Any, Callable, Type

from objinspect import Class, Function, Method, Parameter, inspect
from objinspect.typing import type_args, type_name, type_origin
from strto import StrToTypeParser

from interfacy_cli.argparse_backend.argument_parser import ArgumentParser
from interfacy_cli.argparse_backend.help_formatter import InterfacyHelpFormatter
from interfacy_cli.argparse_backend.runner import ArgparseRunner
from interfacy_cli.argparse_backend.utils import namespace_to_dict
from interfacy_cli.core import ExitCode, InterfacyParserCore
from interfacy_cli.exceptions import (
    DuplicateCommandError,
    InterfacyError,
    InvalidCommandError,
    InvalidConfigurationError,
    ReservedFlagError,
    UnsupportedParameterTypeError,
)
from interfacy_cli.flag_generator import BasicFlagGenerator, FlagGenerator
from interfacy_cli.themes import ParserTheme
from interfacy_cli.util import AbbrevationGenerator, DefaultAbbrevationGenerator


class Argparser(InterfacyParserCore):
    RESERVED_FLAGS = ["h", "help"]
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
        disable_sys_exit: bool = False,
        flag_strategy: FlagGenerator = BasicFlagGenerator(),
        abbrevation_gen: AbbrevationGenerator = DefaultAbbrevationGenerator(),
        pipe_target: dict[str, str] | None = None,
        formatter_class=InterfacyHelpFormatter,
        print_result_func: Callable = print,
    ) -> None:
        super().__init__(
            description,
            epilog,
            theme,
            type_parser,
            run=run,
            allow_args_from_file=allow_args_from_file,
            flag_strategy=flag_strategy,
            abbrevation_gen=abbrevation_gen,
            pipe_target=pipe_target,
            tab_completion=tab_completion,
            print_result=print_result,
            print_result_func=print_result_func,
            full_error_traceback=full_error_traceback,
            disable_sys_exit=disable_sys_exit,
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
        flags = self.flag_strategy.get_arg_flags(name, param, taken_flags, self.abbrevation_gen)
        extra_args = self._extra_add_arg_params(param, flags)
        return parser.add_argument(*flags, **extra_args)

    def _commands_list(self) -> list[Function | Class | Method]:
        return list(self.commands.values())

    def add_command(self, command: Callable | Any, name: str | None = None):
        obj = inspect(command, inherited=False)
        if name is not None:
            self.flag_strategy.command_translator.add_ignored(name)
        name = name or obj.name
        if name in self.commands:
            raise DuplicateCommandError(name)
        self.commands[name] = obj
        return obj

    def parser_from_function(
        self,
        function: Function,
        parser: ArgumentParser | None = None,
        taken_flags: list[str] | None = None,
    ) -> ArgumentParser:
        """
        Create an ArgumentParser from a Function
        """
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
        """
        Create an ArgumentParser from a Method
        """
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
        """
        Create an ArgumentParser from a Class
        """
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
        command: Function | Method | Class,
        parser: ArgumentParser | None = None,
        subparser=None,
    ):
        if isinstance(command, Method):
            return self.parser_from_method(
                command,
                taken_flags=[*self.RESERVED_FLAGS],
                parser=parser,
            )
        if isinstance(command, Function):
            return self.parser_from_function(
                command,
                taken_flags=[*self.RESERVED_FLAGS],
                parser=parser,
            )
        if isinstance(command, Class):
            return self.parser_from_class(command, parser=parser, subparser=subparser)
        raise InvalidCommandError(command)

    def parser_from_multiple_commands(
        self,
        commands: dict[str, Function | Method | Class],
        parser: ArgumentParser | None = None,
    ) -> ArgumentParser:
        parser = parser or self._new_parser()
        parser.epilog = self.theme.get_help_for_multiple_commands(commands)
        subparsers = parser.add_subparsers(dest=self.COMMAND_KEY, required=True)

        for name, cmd in commands.items():
            name = self.flag_strategy.command_translator.translate(name)
            sp = subparsers.add_parser(name, description=cmd.description)
            if isinstance(cmd, Function):
                self.parser_from_function(
                    function=cmd, taken_flags=[*self.RESERVED_FLAGS], parser=sp
                )
            elif isinstance(cmd, Class):
                self.parser_from_class(cmd, sp)
            elif isinstance(cmd, Method):
                self.parser_from_method(cmd, taken_flags=[*self.RESERVED_FLAGS], parser=sp)
            else:
                raise InvalidCommandError(cmd)
        return parser

    def _extra_add_arg_params(self, param: Parameter, flags: tuple[str, ...]) -> dict[str, Any]:
        """
        This method creates a dictionary with additional argument parameters needed to
        customize argparse's `add_argument` method based on a given `Parameter` object.

        Args:
            param (Parameter): The parameter for which to construct additional parameters.

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
                t = t_args[0]
                extra["type"] = self.type_parser.get_parse_func(t)
            else:
                extra["type"] = self.type_parser.get_parse_func(param.type)

        if self.theme.clear_metavar:
            if not param.is_required:
                extra["metavar"] = "\b"

        if self.flag_strategy.style == "required_positional":
            is_positional = all([not i.startswith("-") for i in flags])
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

    def build_parser(self):
        if not self.commands:
            raise InvalidConfigurationError("No commands were provided")

        commands_list = self._commands_list()
        if len(commands_list) == 1:
            command = commands_list.pop()
            parser = self.parser_from_command(command)
        else:
            parser = self.parser_from_multiple_commands(self.commands)

        if self.description:
            parser.description = self.theme.format_description(self.description)

        if self.enable_tab_completion:
            self.install_tab_completion(parser)
        return parser

    def parse_args(self, args: list[str] | None = None):
        args = args if args is not None else self.get_args()
        parser = self.build_parser()
        self._parser = parser
        parsed = parser.parse_args(args)
        namespace = namespace_to_dict(parsed)
        if self.COMMAND_KEY in namespace:
            command = namespace[self.COMMAND_KEY]
            namespace[command] = namespace[command]
        return namespace

    def _display_error(self, e: Exception, message: str):
        exception_str = f'{type_name(str(type(e)))}("{str(e)}")'
        message += f": {exception_str}"

        if self.full_error_traceback:
            import traceback

            print(traceback.format_exc(), file=sys.stderr)
        self.log_err(message)

    def run(self, *commands: Callable | Type | object, args: list[str] | None = None) -> Any:
        try:
            for i in commands:
                self.add_command(i)
            args = args if args is not None else self.get_args()
            namespace = self.parse_args(args)
        except (
            DuplicateCommandError,
            UnsupportedParameterTypeError,
            ReservedFlagError,
            InvalidCommandError,
            InvalidConfigurationError,
        ) as e:
            self._display_error(e, "Failed to parse command-line arguments")
            self.exit(ExitCode.ERR_PARSING)
            return e

        try:
            runner = ArgparseRunner(
                self.commands,
                namespace=namespace,
                args=args,
                parser=self._parser,
                builder=self,
            )
            result = runner.run()
        except InterfacyError as e:
            self._display_error(e, "")
            self.exit(ExitCode.ERR_RUNTIME_INTERNAL)
            return e

        except Exception as e:
            self._display_error(
                e,
                "Unexpected error occurred",
            )
            self.exit(ExitCode.ERR_RUNTIME)
            return e

        if self.display_result:
            self.result_display_fn(result)

        self.exit(ExitCode.SUCCESS)
        return result

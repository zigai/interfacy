import argparse
import re
import sys
import textwrap
import typing as T
from argparse import ArgumentError, ArgumentParser, ArgumentTypeError, HelpFormatter, Namespace

from nested_argparse import NestedArgumentParser
from objinspect import Class, Function, Method, Parameter, inspect
from objinspect._class import split_init_args
from objinspect.method import split_args_kwargs
from objinspect.typing import type_args, type_name, type_origin
from strto import StrToTypeParser

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
from interfacy_cli.themes import DefaultTheme
from interfacy_cli.util import (
    AbbrevationGenerator,
    DefaultAbbrevationGenerator,
    revese_arg_translations,
)

try:
    from gettext import gettext as _
except ImportError:

    def _(message):
        return message


def namespace_to_dict(namespace: Namespace) -> dict[str, T.Any]:
    result = {}
    for key, value in vars(namespace).items():
        if isinstance(value, Namespace):
            result[key] = namespace_to_dict(value)
        else:
            result[key] = value
    return result


class ArgumentParserWrapper(NestedArgumentParser):
    def __init__(
        self,
        name: str | None = None,
        prog=None,
        nest_dir=None,
        nest_separator="__",
        nest_path=None,
        usage=None,
        description=None,
        epilog=None,
        parents=[],
        formatter_class=argparse.HelpFormatter,
        prefix_chars="-",
        fromfile_prefix_chars=None,
        argument_default=None,
        conflict_handler="error",
        add_help=True,
        allow_abbrev=True,
    ):
        super().__init__(
            prog,
            nest_dir,
            nest_separator,
            nest_path,
            usage,
            description,
            epilog,
            parents,
            formatter_class,
            prefix_chars,
            fromfile_prefix_chars,
            argument_default,
            conflict_handler,
            add_help,
            allow_abbrev,
        )
        self.name = name

    def _get_value(self, action, arg_string):
        parse_func = self._registry_get("type", action.type, action.type)
        if not callable(parse_func):
            msg = _("%r is not callable")
            raise ArgumentError(action, msg % parse_func)
        try:
            result = parse_func(arg_string)

        # ArgumentTypeErrors indicate errors
        except ArgumentTypeError:
            name = getattr(action.type, "__name__", repr(action.type))
            msg = str(sys.exc_info()[1])
            raise ArgumentError(action, msg)

        # TypeErrors or ValueErrors also indicate errors
        except (TypeError, ValueError):
            t = type_name(str(parse_func.keywords["t"]))
            msg = _(f"invalid {t} value: '{arg_string}'")
            raise ArgumentError(action, msg)
        return result


class SafeHelpFormatter(HelpFormatter):
    """
    Helpstring formatter that doesn't crash your program if your terminal windows isn't wide enough.
    Explained here: https://stackoverflow.com/a/50394665/18588657
    """

    def _format_usage(self, usage, actions, groups, prefix):
        if prefix is None:
            prefix = _("usage: ")
        # if usage is specified, use that
        if usage is not None:
            usage = usage % dict(prog=self._prog)
        # if no optionals or positionals are available, usage is just prog
        elif usage is None and not actions:
            usage = "%(prog)s" % dict(prog=self._prog)
        # if optionals and positionals are available, calculate usage
        elif usage is None:
            prog = "%(prog)s" % dict(prog=self._prog)
            # split optionals from positionals
            optionals = []
            positionals = []
            for action in actions:
                if action.option_strings:
                    optionals.append(action)
                else:
                    positionals.append(action)

            # build full usage string
            format = self._format_actions_usage
            action_usage = format(optionals + positionals, groups)
            usage = " ".join([s for s in [prog, action_usage] if s])

            # wrap the usage parts if it's too long
            text_width = self._width - self._current_indent
            if len(prefix) + len(usage) > text_width:
                # break usage into wrappable parts
                part_regexp = r"\(.*?\)+(?=\s|$)|" r"\[.*?\]+(?=\s|$)|" r"\S+"
                opt_usage = format(optionals, groups)
                pos_usage = format(positionals, groups)
                opt_parts = re.findall(part_regexp, opt_usage)
                pos_parts = re.findall(part_regexp, pos_usage)

                # NOTE: only change from original code is commenting out the assert statements
                # assert " ".join(opt_parts) == opt_usage
                # assert " ".join(pos_parts) == pos_usage

                # helper for wrapping lines
                def get_lines(parts, indent, prefix=None):
                    lines, line = [], []
                    if prefix is not None:
                        line_len = len(prefix) - 1
                    else:
                        line_len = len(indent) - 1
                    for part in parts:
                        if line_len + 1 + len(part) > text_width and line:
                            lines.append(indent + " ".join(line))
                            line = []
                            line_len = len(indent) - 1
                        line.append(part)
                        line_len += len(part) + 1
                    if line:
                        lines.append(indent + " ".join(line))
                    if prefix is not None:
                        lines[0] = lines[0][len(indent) :]
                    return lines

                # if prog is short, follow it with optionals or positionals
                if len(prefix) + len(prog) <= 0.75 * text_width:
                    indent = " " * (len(prefix) + len(prog) + 1)
                    if opt_parts:
                        lines = get_lines([prog] + opt_parts, indent, prefix)
                        lines.extend(get_lines(pos_parts, indent))
                    elif pos_parts:
                        lines = get_lines([prog] + pos_parts, indent, prefix)
                    else:
                        lines = [prog]

                # if prog is long, put it on its own line
                else:
                    indent = " " * len(prefix)
                    parts = opt_parts + pos_parts
                    lines = get_lines(parts, indent)
                    if len(lines) > 1:
                        lines = []
                        lines.extend(get_lines(opt_parts, indent))
                        lines.extend(get_lines(pos_parts, indent))
                    lines = [prog] + lines

                # join lines into usage
                usage = "\n".join(lines)

        # prefix with 'usage:'
        return "%s%s\n\n" % (prefix, usage)


class SafeRawHelpFormatter(SafeHelpFormatter):
    def _fill_text(self, text, width, indent):
        """
        Doesn't strip whitespace from the beginning of the line when formatting help text.

        Code from: https://stackoverflow.com/a/74368128/18588657
        """
        # Strip the indent from the original python definition that plagues most of us.
        text = textwrap.dedent(text)
        text = textwrap.indent(text, indent)  # Apply any requested indent.
        text = text.splitlines()  # Make a list of lines
        text = [textwrap.fill(line, width) for line in text]  # Wrap each line
        text = "\n".join(text)  # Join the lines again
        return text

    def _split_lines(self, text, width):
        return text.splitlines()


class Argparser(InterfacyParserCore):
    RESERVED_FLAGS = ["h", "help"]
    COMMAND_KEY = "command"

    def __init__(
        self,
        description: str | None = None,
        epilog: str | None = None,
        type_parser: StrToTypeParser | None = None,
        theme: DefaultTheme | None = None,
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
        formatter_class=SafeRawHelpFormatter,
        print_result_func: T.Callable = print,
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
        return ArgumentParserWrapper(name, formatter_class=self.formatter_class)

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

    def add_command(self, command: T.Callable | T.Any, name: str | None = None):
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

    def _extra_add_arg_params(self, param: Parameter, flags: tuple[str, ...]) -> dict[str, T.Any]:
        """
        This method creates a dictionary with additional argument parameters needed to
        customize argparse's `add_argument` method based on a given `Parameter` object.

        Args:
            param (Parameter): The parameter for which to construct additional parameters.

        Returns:
            dict[str, Any]: A dictionary containing additional parameter settings like "help",
            "required", "metavar", and "default".

        """
        extra: dict[str, T.Any] = {}
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

        """
        if self.theme.clear_metavar:
            extra["metavar"] = "\b"
        del extra["metavar"]
        """

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

    def _display_err(self, e: Exception, message: str):
        exception_str = f'{type_name(str(type(e)))}("{str(e)}")'
        message += f": {exception_str}"

        if self.full_error_traceback:
            import traceback

            print(traceback.format_exc(), file=sys.stderr)
            self.log_err(message)
        else:
            self.log_err(message)
            self.log_err("To see the full traceback enable 'full_error_traceback'")

    def run(self, *commands: T.Callable, args: list[str] | None = None) -> T.Any:
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
            self._display_err(e, "Failed to parse command-line arguments")
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
            self._display_err(e, "")
            self.exit(ExitCode.ERR_RUNTIME_INTERNAL)
            return e
        except Exception as e:
            self._display_err(
                e,
                "Unexpected error occurred. Likely an issue with Interfacy, not user input",
            )
            self.exit(ExitCode.ERR_RUNTIME)
            return e

        if self.display_result:
            self.result_display_fn(result)

        self.exit(ExitCode.SUCCESS)
        return result


class ArgparseRunner:
    def __init__(
        self,
        commands: dict[str, Function | Class | Method],
        namespace: dict,
        builder: Argparser,
        args: list[str],
        parser,
    ) -> None:
        self._parser = parser
        self.commands = commands
        self.namespace = namespace
        self.args = args
        self.builder = builder
        self.COMMAND_KEY = self.builder.COMMAND_KEY

    def run(self):
        if len(self.commands) == 0:
            raise InvalidConfigurationError("No commands were provided")
        if len(self.commands) == 1:
            command = list(self.commands.values())[0]
            return self.run_command(command, self.namespace)
        return self.run_multiple(self.commands)

    def run_command(self, command: Function | Method | Class, args: dict):
        handler = {
            Function: self.run_function,
            Method: self.run_method,
            Class: self.run_class,
        }
        t = type(command)
        if t not in handler:
            raise InvalidCommandError(command)
        return handler[t](command, args)

    def run_function(self, func: Function | Method, args: dict) -> T.Any:
        func_args, func_kwargs = split_args_kwargs(args, func)
        return func.call(*func_args, **func_kwargs)

    def run_method(self, method: Method, args: dict) -> T.Any:
        cli_args = revese_arg_translations(args, self.builder.flag_strategy.argument_translator)
        instance = method.class_instance
        if instance:
            method_args, method_kwargs = split_args_kwargs(cli_args, method)
            return method.call(*method_args, **method_kwargs)

        instance = Class(method.cls)
        args_init, args_method = split_init_args(cli_args, instance, method)
        init_args, init_kwargs = split_args_kwargs(args_init, method)
        instance.init(*init_args, **init_kwargs)
        method_args, method_kwargs = split_args_kwargs(args_method, method)
        return instance.call_method(method.name, *method_args, **method_kwargs)

    def run_class(self, cls: Class, args: dict) -> T.Any:
        command_name = args[self.COMMAND_KEY]
        command_args = args[command_name]
        del args[self.COMMAND_KEY]
        del args[command_name]

        if cls.init_method and not cls.is_initialized:
            init_args, init_kwargs = split_args_kwargs(args, cls.init_method)
            cls.init(*init_args, **init_kwargs)

        method_args, method_kwargs = split_args_kwargs(command_args, cls.get_method(command_name))
        return cls.call_method(command_name, *method_args, **method_kwargs)

    def run_multiple(self, commands: dict[str, Function | Class | Method]) -> T.Any:
        command_name = self.namespace[self.COMMAND_KEY]
        command = commands[command_name]
        args = self.namespace[command_name]
        return self.run_command(command, args)


__all__ = ["Argparser", "ArgparseRunner"]

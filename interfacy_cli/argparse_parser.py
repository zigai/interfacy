import argparse
import re
import sys
import textwrap
import typing as T
from argparse import ArgumentError, ArgumentParser, ArgumentTypeError, HelpFormatter
from copy import deepcopy

from nested_argparse import NestedArgumentParser
from objinspect import Class, Function, Method, Parameter, inspect
from objinspect._class import split_init_args
from objinspect.method import split_args_kwargs
from objinspect.typing import type_name
from strto import StrToTypeParser

from interfacy_cli.core import (
    DefaultFlagStrategy,
    ExitCode,
    FlagStrategyProtocol,
    InterfacyParserCore,
)
from interfacy_cli.exceptions import InvalidCommandError, ReservedFlagError, UnsupportedParamError
from interfacy_cli.themes import InterfacyTheme
from interfacy_cli.util import AbbrevationGeneratorProtocol, DefaultAbbrevationGenerator

try:
    from gettext import gettext as _
except ImportError:

    def _(message):
        return message


class ArgumentParserWrapper(NestedArgumentParser):
    def __init__(
        self,
        name: str = None,
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


COMMAND_KEY = "command"


class ArgparseParser(InterfacyParserCore):
    RESERVED_FLAGS = ["h", "help"]

    def __init__(
        self,
        description: str | None = None,
        epilog: str | None = None,
        theme: InterfacyTheme | None = None,
        type_parser: StrToTypeParser | None = None,
        *,
        run: bool = False,
        allow_args_from_file: bool = True,
        flag_strategy: FlagStrategyProtocol = DefaultFlagStrategy(),
        abbrev_gen: AbbrevationGeneratorProtocol = DefaultAbbrevationGenerator(),
        pipe_target: dict[str, str] | None = None,
        tab_completion: bool = False,
        formatter_class=SafeRawHelpFormatter,
        print_result: bool = False,
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
            abbrev_gen=abbrev_gen,
            pipe_target=pipe_target,
            tab_completion=tab_completion,
            print_result=print_result,
            print_result_func=print_result_func,
        )
        self.formatter_class = formatter_class
        self._parser = self._new_parser(name="main")
        self._subparsers = self._parser.add_subparsers(dest=COMMAND_KEY, required=True)

    def _new_parser(self, name: str = None):
        return ArgumentParserWrapper(name, formatter_class=self.formatter_class)

    def _add_parameter_to_parser(
        self,
        parser: ArgumentParser,
        param: Parameter,
        taken_flags: list[str],
    ):
        if param.name in taken_flags:
            raise ReservedFlagError(param.name)
        name = self.flag_strategy.arg_translator.translate(param.name)
        flags = self.flag_strategy.get_arg_flags(name, param, taken_flags, self.abbrev_gen)
        extra_args = self._extra_add_arg_params(param)
        return parser.add_argument(*flags, **extra_args)

    def _parser_from_func(
        self,
        fn: Function,
        taken_flags: list[str] | None = None,
        parser: ArgumentParser | None = None,
    ) -> ArgumentParser:
        """
        Create an ArgumentParser from a Function
        """
        if taken_flags is None:
            taken_flags = []
        if parser is None:
            parser = self._new_parser()
        if fn.has_docstring:
            parser.description = self.theme.format_description(fn.description)
        for param in fn.params:
            self._add_parameter_to_parser(parser, param, taken_flags)
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
        if parser is None:
            parser = self._new_parser()
        for param in method.params:
            self._add_parameter_to_parser(parser, param, taken_flags)

        if method.has_docstring:
            parser.description = self.theme.format_description(method.description)

        obj_class = Class(method.cls)
        init = obj_class.init_method
        if init is None:
            return parser

        for param in init.params:
            self._add_parameter_to_parser(parser, param, taken_flags)
        return parser

    def _parser_from_class(
        self,
        cls: Class,
        parser: ArgumentParser | None = None,
        subparser=None,
    ) -> ArgumentParser:
        """
        Create an ArgumentParser from a Class
        """
        print(cls)
        if parser is None:
            parser = self._new_parser()

        if cls.has_docstring:
            parser.description = self.theme.format_description(cls.description)
        parser.epilog = self.theme.get_commands_help_class(cls)  # type: ignore

        if cls.has_init and not cls.is_initialized:
            init = cls.get_method("__init__")
            for i in init.params:
                self._add_parameter_to_parser(
                    parser, param=i, taken_flags=[*self.RESERVED_FLAGS, COMMAND_KEY]
                )

        if subparser is None:
            subparser = parser.add_subparsers(dest=COMMAND_KEY, required=True)

        for method in cls.methods:
            if method.name in self.method_skips:
                continue
            taken_flags = [*self.RESERVED_FLAGS]

            method_name = self.flag_strategy.command_translator.translate(method.name)
            sp = subparser.add_parser(method_name, description=method.description)
            sp = self._parser_from_func(method, taken_flags, sp)
        return parser

    def _parser_from_multiple(
        self,
        commands: list[Function | Method | Class],
    ) -> ArgumentParser:
        parser = self._new_parser()
        parser.epilog = self.theme.get_commands_help_multiple(commands)
        subparsers = parser.add_subparsers(dest=COMMAND_KEY, required=True)

        for cmd in commands:
            command_name = self.flag_strategy.command_translator.translate(cmd.name)
            sp = subparsers.add_parser(command_name, description=cmd.description)
            if isinstance(cmd, Function):
                sp = self._parser_from_func(fn=cmd, taken_flags=[*self.RESERVED_FLAGS], parser=sp)
            elif isinstance(cmd, Class):
                sp = self._parser_from_class(cmd, sp)
            elif isinstance(cmd, Method):
                sp = self.parser_from_method(cmd, taken_flags=[*self.RESERVED_FLAGS], parser=sp)
            else:
                raise InvalidCommandError(f"Not a valid command: {cmd}")
        return parser

    def _parser_from_object(self, obj: Function | Method | Class, main: bool = False):
        if isinstance(obj, (Function, Method)):
            return self._parser_from_func(obj, taken_flags=[*self.RESERVED_FLAGS])
        if isinstance(obj, Class):
            extra = {}
            if main:
                extra["parser"] = self._parser
                extra["subparser"] = self._subparsers
            else:
                extra = {}
            return self._parser_from_class(obj, **extra)
        raise InvalidCommandError(f"Not a valid command: {obj}")

    def _extra_add_arg_params(self, param: Parameter) -> dict[str, T.Any]:
        """
        This method creates a dictionary with additional argument parameters needed to
        customize argparse's `add_argument` method based on a given `Parameter` object.

        Args:
            param (Parameter): The parameter for which to construct additional parameters.

        Returns:
            dict[str, Any]: A dictionary containing additional parameter settings like "help",
            "required", "metavar", and "default".

        """
        help_str = self.theme.get_parameter_help(param)
        extra: dict[str, T.Any] = {}
        extra["help"] = help_str

        if param.is_typed:
            extra["type"] = self.type_parser.get_parse_func(param.type)

        if self.theme.clear_metavar:
            extra["metavar"] = "\b"

        if self.flag_strategy.flags_style == "required_positional":
            if not param.is_required:
                extra["required"] = param.is_required  # type:ignore
            else:
                del extra["metavar"]
        else:
            pass
            # extra["required"] = param.is_required  # type:ignore

        # Handle boolean parameters
        if param.is_typed and type(param.type) is bool:
            if param.is_required or param.default == False:
                extra["default"] = "store_true"
            else:
                extra["default"] = "store_false"
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

    def add_command(self, command: T.Callable, name: str | None = None):
        obj = inspect(command, inherited=False)
        name = name or obj.name
        sp = self._subparsers.add_parser(name)
        sp = self._parser_from_object(obj, main=False)
        return sp

    def parse_args(self, args: list[str] | None = None):
        args = args or self.get_args()
        return self._parser.parse_args()

    def run(self, *commands: T.Callable, args: list[str] | None = None) -> T.Any:
        args = args or self.get_args()
        commands_dict = self._collect_commands(*commands)
        runner = ArgparseRunner(commands_dict, args=args, builder=self, run=False)
        result = runner.run()
        if self.print_result:
            self.print_result_func(result)
        return result


class ArgparseRunner:
    def __init__(
        self,
        commands: dict[str, Function | Class | Method],
        builder: ArgparseParser,
        args: list[str],
        run: bool = True,
    ) -> None:
        self.commands = commands
        self.run_cli = run
        self.args = args
        self.builder = builder

        if self.run_cli:
            self.run()

    def run(self):
        if len(self.commands) == 0:
            raise InvalidCommandError("No commands were provided.")

        elif len(self.commands) == 1:
            command = list(self.commands.values())[0]
            if isinstance(command, Function):
                return self._run_callable(command)
            if isinstance(command, Class):
                return self._run_class(command)
            if isinstance(command, Method):
                return self._run_method(command)
            raise InvalidCommandError(f"Not a valid command: {command}")
        return self._run_multiple(self.commands)

    def setup_parser(self, parser) -> None:
        if self.builder.description:
            parser.description = self.builder.theme.format_description(self.builder.description)

        if self.builder.enable_tab_completion:
            self.builder.install_tab_completion(parser)

    def _run_callable(self, func: Function | Method) -> T.Any:
        """
        Called when a single function or method is passed to CLI
        """
        builder = self.builder
        parser = builder._parser_from_func(func, [*self.builder.RESERVED_FLAGS])
        self.setup_parser(parser)

        args = parser.parse_args(self.args)
        args, kwargs = split_args_kwargs(vars(args), func)
        return func.call(*args, **kwargs)

    def _run_method(self, method: Method) -> T.Any:
        """
        Called when a single method is passed to CLI
        """
        builder = self.builder
        parser = builder.parser_from_method(method, [*self.builder.RESERVED_FLAGS])
        self.setup_parser(parser)

        args = parser.parse_args(self.args)
        args_all = self.revese_arg_translations(vars(args))
        obj = Class(method.cls)
        args_init, args_method = split_init_args(args_all, obj, method)
        obj.init(**args_init)
        return obj.call_method(method.name, **args_method)

    def _run_class(self, cls: Class):
        builder = self.builder
        parser = builder._parser_from_class(cls)
        self.setup_parser(parser)
        args = parser.parse_args(self.args)
        return self._run_class_inner(cls, vars(args), parser)

    def _run_multiple(self, commands: dict[str, Function | Class]) -> T.Any:
        builder = self.builder
        parser = builder._parser_from_multiple(commands.values())  # type: ignore
        self.setup_parser(parser)
        args = parser.parse_args(self.args)
        args = vars(args)

        if COMMAND_KEY not in args:
            parser.print_help()
            sys.exit(ExitCode.INVALID_ARGS_ERR)

        command_name = args[COMMAND_KEY]
        command_args = vars(args[command_name])
        init_args = deepcopy(args)
        del init_args[COMMAND_KEY]
        del init_args[command_name]

        command_name = (
            self.builder.flag_strategy.command_translator.reverse(command_name) or command_name
        )
        cmd = commands[command_name]
        if isinstance(cmd, (Function, Method)):
            return cmd.call(**command_args)
        elif isinstance(cmd, Class):
            return self._run_class_inner(cmd, command_args, parser)
        else:
            raise InvalidCommandError(f"Not a valid command: {cmd}")

    def _run_class_inner(self, cls: Class, args: dict, parser: ArgumentParser):
        if COMMAND_KEY not in args:
            parser.print_help()
            sys.exit(ExitCode.INVALID_ARGS_ERR)

        command_name = args[COMMAND_KEY]
        command_args = vars(args[command_name])
        init_args = deepcopy(args)
        del init_args[COMMAND_KEY]
        del init_args[command_name]

        command_name = (
            self.builder.flag_strategy.command_translator.reverse(command_name) or command_name
        )
        method = cls.get_method(command_name)
        args_for_method = self.revese_arg_translations(command_args)

        if cls.has_init and not method.is_static:
            cls.init(**init_args)

        return cls.call_method(command_name, **args_for_method)

    def revese_arg_translations(self, args: dict) -> dict[str, T.Any]:
        reversed = {}
        for k, v in args.items():
            k = self.builder.flag_strategy.arg_translator.reverse(k)
            reversed[k] = v
        return reversed


__all__ = ["ArgparseParser", "ArgparseRunner"]

import re
import sys
import textwrap
import typing as T
from argparse import ArgumentError, ArgumentParser, ArgumentTypeError, HelpFormatter
from functools import partial

import strto
from nested_argparse import NestedArgumentParser
from objinspect import Class, Function, Method, Parameter
from stdl.st import kebab_case, snake_case
from strto.util import type_to_str

from interfacy_cli.auto_parser_core import AutoParserCore, FlagsStrategy
from interfacy_cli.constants import COMMAND_KEY, RESERVED_FLAGS
from interfacy_cli.exceptions import InvalidCommandError, ReservedFlagError
from interfacy_cli.themes import InterfacyTheme

try:
    from gettext import gettext as _
except ImportError:

    def _(message):
        return message


class ArgumentParserWrapper(NestedArgumentParser):
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
            t = type_to_str(str(parse_func.keywords["t"]))
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


class AutoArgparseParser(AutoParserCore):
    flag_translate_fn = {"none": lambda s: s, "kebab": kebab_case, "snake": snake_case}
    method_skips = ["__init__"]
    log_msg_tag = "interfacy"

    def __init__(
        self,
        description: str | None = None,
        epilog: str | None = None,
        theme: InterfacyTheme | None = None,
        value_parser: strto.Parser | None = None,
        formatter_class=SafeRawHelpFormatter,
        *,
        flag_strategy: T.Literal["keyword_only", "required_positional"] = "required_positional",
        flag_translation_mode: T.Literal["none", "kebab", "snake"] = "kebab",
        from_file_prefix: str = "@F",
        display_result: bool = True,
        add_abbrevs: bool = True,
        read_stdin: bool = False,
        allow_args_from_file: bool = True,
    ):
        super().__init__(
            description,
            epilog,
            theme,
            value_parser,
            flag_strategy=flag_strategy,
            flag_translation_mode=flag_translation_mode,
            from_file_prefix=from_file_prefix,
            add_abbrevs=add_abbrevs,
            read_stdin=read_stdin,
            display_result=display_result,
            allow_args_from_file=allow_args_from_file,
        )
        self.formatter_class = formatter_class
        self._main_parser = self._new_parser()
        self.set_description(description)
        self.set_epilog(epilog)

    @property
    def parser(self) -> NestedArgumentParser:
        return self._main_parser

    def _new_parser(self):
        return ArgumentParserWrapper(formatter_class=self.formatter_class)

    def set_description(self, description: str | None = None) -> None:
        self._main_parser.description = description

    def set_epilog(self, epilog: str | None = None) -> None:
        self._main_parser.epilog = epilog

    def add_argument(self, *args, **kwargs):
        if "type" in kwargs:
            func = partial(self.value_parser.parse, t=kwargs["type"])
            kwargs["type"] = func
        return self._main_parser.add_argument(*args, **kwargs)

    def parse_args(self, args: list[str] | None = None):
        if args is None:
            args = self.get_args()
        return self._main_parser.parse_args(args)

    def add_subparsers(self, *args, **kwargs):
        return self._main_parser.add_subparsers(*args, **kwargs)

    def add_parameter(
        self,
        parser: ArgumentParser,
        param: Parameter,
        taken_flags: list[str],
    ):
        if param.name in taken_flags:
            raise ReservedFlagError(param.name)
        name = self.name_translator(param.name)
        flags = self._get_arg_flags(name, param, taken_flags)
        extra_args = self._extra_add_arg_params(param)
        return parser.add_argument(*flags, **extra_args)

    def parser_from_func(
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
        for param in fn.params:
            self.add_parameter(parser, param, taken_flags)
        if fn.has_docstring:
            parser.description = self.theme.format_description(fn.description)
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
            self.add_parameter(parser, param, taken_flags)

        if method.has_docstring:
            parser.description = self.theme.format_description(method.description)

        obj_class = Class(method.cls)

        init = obj_class.init_method
        if init is None:
            return parser

        for param in init.params:
            self.add_parameter(parser, param, taken_flags)
        return parser

    def parser_from_class(
        self,
        cls: Class,
        parser: ArgumentParser | None = None,
    ) -> ArgumentParser:
        """
        Create an ArgumentParser from a Class
        """
        if parser is None:
            parser = self._new_parser()
        if cls.has_init and not cls.is_initialized:
            init = cls.get_method("__init__")
        if cls.has_docstring:
            parser.description = self.theme.format_description(cls.description)

        parser.epilog = self.theme.get_commands_help_class(cls)  # type: ignore

        subparsers = parser.add_subparsers(dest=COMMAND_KEY, required=True)
        for method in cls.methods:
            if method.name in self.method_skips:
                continue
            taken_flags = [*RESERVED_FLAGS]
            method_name = self.name_translator(method.name)

            sp = subparsers.add_parser(method_name, description=method.description)
            if cls.has_init and not cls.is_initialized and not method.is_static:
                for param in init.params:  # type: ignore
                    self.add_parameter(sp, param, taken_flags=taken_flags)
            sp = self.parser_from_func(method, taken_flags, sp)
        return parser

    def parser_from_multiple(
        self,
        commands: list[Function | Class],
    ) -> ArgumentParser:
        parser = self._new_parser()
        parser.epilog = self.theme.get_commands_help_multiple(commands)
        subparsers = parser.add_subparsers(dest=COMMAND_KEY, required=True)

        for cmd in commands:
            command_name = self.name_translator(cmd.name)
            sp = subparsers.add_parser(command_name, description=cmd.description)
            if isinstance(cmd, Function):
                sp = self.parser_from_func(fn=cmd, taken_flags=[*RESERVED_FLAGS], parser=sp)
            elif isinstance(cmd, Class):
                sp = self.parser_from_class(cmd, sp)
            elif isinstance(cmd, Method):
                sp = self.parser_from_method(cmd, sp)
            else:
                raise InvalidCommandError(f"Not a valid command: {cmd}")
        return parser

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
        extra = {"help": self.theme.get_parameter_help(param)}

        if self.theme.clear_metavar:
            extra["metavar"] = "\b"

        if self.flag_strategy == FlagsStrategy.REQUIRED_POSITIONAL:
            if not param.is_required:
                extra["required"] = param.is_required  # type:ignore
            else:
                del extra["metavar"]
        else:
            extra["required"] = param.is_required  # type:ignore

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


__all__ = ["AutoArgparseParser"]

import argparse
import sys
from argparse import ArgumentParser
from pprint import pp, pprint
from typing import Any, Callable

from nested_argparse import NestedArgumentParser
from objinspect import Class, Function, Parameter, objinspect
from objinspect.util import call_method

from interfacy_cli.constants import RESERVED_FLAGS
from interfacy_cli.exceptions import ReservedFlagError, UnsupportedParamError
from interfacy_cli.parser import PARSER
from interfacy_cli.themes import DefaultTheme, Theme


def get_command_short_name(name: str, taken: list[str]) -> str | None:
    """
    Tries to return a short name for a command.
    Returns None if it cannot find a short name.

    Example:
        >>> get_command_short_name("hello_world", [])
        >>> "h"
        >>> get_command_short_name("hello_world", ["h"])
        >>> "hw"
        >>> get_command_short_name("hello_world", ["hw", "h"])
        >>> "he"
        >>> get_command_short_name("hello_world", ["hw", "h", "he"])
        >>> None
    """
    if name in taken:
        raise ValueError(f"Command name '{name}' already taken")
    if len(name) < 3:
        return name
    name_split = name.split("_")
    if name_split[0][0] not in taken:
        taken.append(name_split[0][0])
        return name_split[0][0]
    short_name = "".join([i[0] for i in name_split])
    if short_name not in taken:
        taken.append(short_name)
        return short_name
    try:
        short_name = name_split[0][:2]
        if short_name not in taken:
            taken.append(short_name)
            return short_name
        return None
    except IndexError:
        return None


class CLI:
    def __init__(
        self,
        *commands: Callable,
        shorten_command_names: bool = True,
        theme: Theme | None = None,
        run: bool = True,
        print_result: bool = False,
        description: str | None = None,
    ) -> None:
        self.commands: list = []
        for i in commands:
            self.commands.append(i)

        self.shorten_command_names = shorten_command_names
        self.description = description
        self.theme = theme or DefaultTheme()
        self.print_result = print_result
        if run:
            self.run()

    def get_args(self):
        return sys.argv[1:]

    def _get_new_parser(self):
        return NestedArgumentParser(formatter_class=self.theme.formatter_class)

    def _run(self) -> Any:
        commands: dict[str, Function | Class] = {}
        for i in self.commands:
            c = objinspect(i, inherited=False)
            if c.name in commands:
                raise KeyError(f"Duplicate command '{c.name}'")
            commands[c.name] = c

        if len(commands) == 1:
            cmd = list(commands.values())[0]
            if isinstance(cmd, Function):
                return self._single_func_command(cmd)
            if isinstance(cmd, Class):
                return self._single_class_command(cmd)
            raise ValueError(cmd)

        parser = self._get_new_parser()
        parser.epilog = self.theme.get_top_level_epilog(*commands.values())
        subparsers = parser.add_subparsers(dest="command")

        for cmd in commands.values():
            p = subparsers.add_parser(cmd.name, description=cmd.description)
            if isinstance(cmd, Function):
                p = self.parser_from_func(cmd, p)
            elif isinstance(cmd, Class):
                p = self.parser_from_class(cmd, p)
            else:
                raise TypeError(cmd)
        args = parser.parse_args()
        print(self.get_args())
        print(commands)
        print(args)
        method = args.command
        obj_args = args.__dict__
        del obj_args["command"]

    def run(self) -> Any:
        res = self._run()
        if self.print_result:
            pprint(res)

    def _single_func_command(self, func: Function):
        """
        Called when a single function or method is passed to CLI
        """
        ap = self.parser_from_func(func)
        if self.description:
            ap.description = self.theme.format_description(self.description)
        args = ap.parse_args(self.get_args())
        args_dict = args.__dict__
        for name, value in args_dict.items():
            args_dict[name] = PARSER.parse(value=value, t=func.get_param(name).type)
        return func.func(**args_dict)

    def _single_class_command(self, cls: Class):
        parser = self.parser_from_class(cls)
        if self.description:
            parser.description = self.theme.format_description(self.description)
        args = parser.parse_args(self.get_args())
        obj_args = args.__dict__
        method = args.command
        method_args = obj_args[method].__dict__
        del obj_args[method]
        del obj_args["command"]
        obj = cls.cls(**obj_args)
        return call_method(obj, method, kwargs=method_args)

    def parser_from_func(self, f: Function, parser: ArgumentParser | None = None) -> ArgumentParser:
        """
        Create an ArgumentParser from a Function
        """
        if parser is None:
            parser = self._get_new_parser()
        taken_names = [*RESERVED_FLAGS]

        for param in f.params:
            self.add_parameter(parser, param, taken_names)
        if f.has_docstring:
            parser.description = f.description
        return parser

    def parser_from_class(self, c: Class, parser: ArgumentParser | None = None):
        if parser is None:
            parser = self._get_new_parser()

        if c.has_init and not c.is_initialized:
            init = c.get_method("__init__")
            parser = self.parser_from_func(init, parser)

        parser.epilog = self.theme.get_class_commands_epilog(c)

        cls_methods = c.methods
        # if methods:
        #    cls_methods = [i for i in cls_methods if i.name in methods]
        subparsers = parser.add_subparsers(dest="command")
        for method in cls_methods:
            if method.name == "__init__":
                continue
            p = subparsers.add_parser(method.name, description=method.description)
            p = self.parser_from_func(method, p)
        return parser

    def add_parameter(
        self,
        parser: ArgumentParser,
        param: Parameter,
        taken_names: list[str],
    ):
        if param.name in taken_names:
            raise ReservedFlagError(param.name)
        if not PARSER.is_supported(param.type):
            raise UnsupportedParamError(param.type)

        long_name = f"--{param.name}".strip()
        cmd_names = (long_name,)
        if self.shorten_command_names:
            short_name = get_command_short_name(param.name, taken_names)
            if short_name is not None:
                cmd_names = (long_name, f"-{short_name}".strip())
                cmd_names = (f"-{short_name}".strip(), long_name)

        extra_args = self._extra_add_arg_params(param)
        parser.add_argument(*cmd_names, **extra_args)

    def _extra_add_arg_params(self, param: Parameter) -> dict:
        extra = {
            "help": self.theme.get_parameter_help(param),
            "required": param.is_required,
        }

        if self.theme.clear_metavar:
            extra["metavar"] = "\b"

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


__all__ = ["CLI"]

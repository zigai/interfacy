import argparse
import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from pprint import pp, pprint
from typing import Any, Callable

from nested_argparse import NestedArgumentParser
from py_inspect import Class, Function, Parameter, inspect
from py_inspect.util import call_method

from interfacy_cli.constants import RESERVED_FLAGS
from interfacy_cli.exceptions import ReservedFlagError, UnsupportedParamError
from interfacy_cli.parser import PARSER
from interfacy_cli.themes import Default, Theme


class CLI:
    def __init__(
        self,
        obj,
        *args,
        methods: list[str] | None = None,
        description: str | None = None,
        theme: Theme | None = None,
    ) -> None:

        self.commands: list = [obj]
        self.commands.extend(args)
        self.methods = methods
        self.description = description
        self.theme = Default() if theme is None else theme

    def get_args(self):
        return sys.argv[1:]

    def _get_new_parser(self):
        return NestedArgumentParser(formatter_class=self.theme.formatter_class)

    def run(self) -> Any:
        commands: dict[str, Function | Class] = {}
        for i in self.commands:
            c = inspect(i, include_inherited=False)
            if c.name in commands:
                raise KeyError(f"Duplicate command '{i.name}'")
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
            args_dict[name] = PARSER.parse(val=value, t=func.get_param(name).type)
        return func.func(**args_dict)

    def _single_class_command(self, cls: Class):
        parser = self.parser_from_class(cls, methods=self.methods)
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

        for param in f.params:
            self.add_parameter(parser, param)
        if f.has_docstring:
            parser.description = f.description
        return parser

    def parser_from_class(
        self, c: Class, parser: ArgumentParser | None = None, methods: list[str] | None = None
    ):
        if parser is None:
            parser = self._get_new_parser()

        if c.has_init and not c.initialized:
            init = c.get_method("__init__")
            parser = self.parser_from_func(init, parser)

        parser.epilog = self.theme.get_class_commands_epilog(c)

        cls_methods = c.methods
        if methods:
            cls_methods = [i for i in cls_methods if i.name in methods]
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
        flag_name_prefix: str = "-",
    ):
        if param.name in RESERVED_FLAGS:
            raise ReservedFlagError(param.name)
        if not PARSER.is_supported(param.type):
            raise UnsupportedParamError(param.type)
        extra = self.__extra_add_arg_params(param)
        parser.add_argument(f"{flag_name_prefix}{param.name}", **extra)

    def __extra_add_arg_params(self, param: Parameter) -> dict:
        extra = {
            "help": self.theme.get_parameter_help(param),
            "required": param.is_required,
        }

        if self.theme.clear_metavar:
            extra["metavar"] = ""

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

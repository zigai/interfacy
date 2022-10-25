import argparse
from typing import Any, Callable

from py_inspect import Class, Function, Parameter, inspect

from interfacy_cli.constants import RESERVED_FLAGS
from interfacy_cli.exceptions import ReservedFlagError, UnsupportedParamError
from interfacy_cli.param_helpstring import (
    HelpStringTheme,
    SafeHelpFormatter,
    param_helpstring,
)
from interfacy_cli.parser import PARSER
from interfacy_cli.themes import DEFAULT


class CLI:
    def __init__(
        self,
        func_or_cls,
        methods: list[str] | None = None,
        description: str | None = None,
        theme: HelpStringTheme | None = None,
    ) -> None:

        self.func_or_cls = func_or_cls
        self.methods = methods
        self.description = description
        self.theme = DEFAULT if theme is None else theme
        self.main_parser = argparse.ArgumentParser(formatter_class=SafeHelpFormatter)
        self.specials: dict[str, dict[str, Any]] = {}  # owner[name][type]

    def run(self):
        obj = inspect(self.func_or_cls)
        if isinstance(obj, Function):
            return self.__from_func(obj)
        if isinstance(obj, Class):
            return self.__from_class(obj)

    def __from_func(self, f: Function):
        parser = self.make_parser(f, parser=self.main_parser)
        if self.description:
            parser.description = self.description
        args = parser.parse_args()
        args_dict = args.__dict__
        for name, value in args_dict.items():
            args_dict[name] = PARSER.parse(val=value, t=f.get_param(name).type)
        return f.func(**args_dict)

    def __from_class(self, c: Class):
        if c.has_init:
            parser = self.make_parser(f=c.get_method("__init__"))
            print("!!!")
        else:
            parser = argparse.ArgumentParser(formatter_class=SafeHelpFormatter)
        subparsers = parser.add_subparsers(dest="command")
        for method in c.methods:
            if method.name == "__init__":
                continue
            p = subparsers.add_parser(method.name, description=method.description)

            x = self.make_parser(method, p)
        args = parser.parse_args()
        print(args)

    def make_parser(self, f: Function, parser: argparse.ArgumentParser | None = None):
        """
        Create an ArgumentParser from an InterfacyFunction
        """
        if parser is None:
            parser = argparse.ArgumentParser(formatter_class=SafeHelpFormatter)

        for param in f.params:
            self.add_parameter(parser, param)
        if f.has_docstring:
            parser.description = f.description
        return parser

    def add_parameter(
        self,
        parser: argparse.ArgumentParser,
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
            "help": param_helpstring(param, self.theme),
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

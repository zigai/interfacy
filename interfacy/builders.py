import argparse
import inspect
import types
import typing

from function import InterfacyFunction
from parameter import DEFAULT_CLI_THEME, EMPTY, InterfacyParameter
from parsers import CLI_TYPE_PARSER

RESERVED_FLAGS = ["h", "help", "q", "quiet"]
SIMPLE_TYPES = [str, int, float, bool]


class CLI():

    def __init__(self, func_or_class, class_methods=None, description=None, theme=None) -> None:
        self.func_or_class = func_or_class
        self.class_methods = class_methods
        self.description = description
        self.parser = argparse.ArgumentParser()
        self.theme = DEFAULT_CLI_THEME if theme is None else theme
        self.specials = {}

    def build(self):
        if inspect.isclass(self.func_or_class):  # class
            return self._build_from_class(self.func_or_class, self.class_methods)
        else:  # function
            return self._build_from_function(self.func_or_class)

    def _build_from_class(self, cls, methods):
        pass

    def _build_from_function(self, func):
        func = InterfacyFunction(func)
        if self.description is None:
            self.parser.description = func.docstr
        for param in func.parameters:
            self.add_parameter(self.parser, param, self.theme)
        args = self.parser.parse_args()
        args_dict = args.__dict__
        for name, value in args_dict.items():
            is_special = self.specials.get(name, False)
            if not is_special:
                continue
            var_type = self.specials[name]
            args_dict[name] = CLI_TYPE_PARSER[var_type](value)
        func.func(**args_dict)

    def add_parameter(self, parser: argparse.ArgumentParser, param: InterfacyParameter,
                      theme: dict):
        """Add a parameter to an argument parser"""
        if param.name in RESERVED_FLAGS:
            raise ValueError(param.name)
        param_name = f"--{param.name}"

        if type(param.type) is types.GenericAlias:
            param.type = typing.get_origin(param.type)

        extra = {
            "help": param.get_help_str(self.theme),
            "metavar": "",
            "required": param.is_required
        }

        if param.is_typed and type(param.type) is bool:
            if param.is_required or param.default == False:
                extra["default"] = "store_true"
            else:
                extra["default"] = "store_false"

        if not param.is_required:
            extra["default"] = param.default

        # Handle alias types like int | float
        if type(param.type) is types.UnionType:
            types_list = typing.get_args(param.type)
            types_list = [
                typing.get_origin(i) if type(i) is types.GenericAlias else i for i in types_list
            ]
            types_list = [i for i in types_list if i in SIMPLE_TYPES or i in CLI_TYPE_PARSER]
            if len(types_list) == 0:
                raise TypeError(f"{param.name}: {param.type}")
            parser.add_argument(param_name, **extra)
            self._mark_special(param.name, types_list)
            return

        if param.is_typed:
            extra["type"] = param.type
        else:
            parser.add_argument(param_name, **extra)
            return
        if param.type in SIMPLE_TYPES:
            parser.add_argument(param_name, **extra)
            return
        if param.type in CLI_TYPE_PARSER.keys():
            parser.add_argument(param_name, **extra)
            self._mark_special(param.name, param.type)
            return
        raise TypeError(f"{param.name}: {param.type}")

    def _mark_special(self, name, type):
        if name in self.specials.keys():
            raise ValueError(f"flag '{name}' already used")
        self.specials[name] = type


if __name__ == '__main__':
    import pretty_errors

    from testing_functions import *
    CLI(test_func1).build()

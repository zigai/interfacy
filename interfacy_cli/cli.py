import argparse
import enum
import inspect
import types
import typing
from pprint import pp, pprint
from typing import Any

import pretty_errors

import interfacy_cli.cli.themes as CLI_THEMES
from interfacy_cli.cli.helpstr_theme import HelpStringTheme
from interfacy_cli.cli.parsers import CLI_PARSER
from interfacy_cli.constants import SPECIAL_GENERIC_ALIAS, UNION_GENERIC_ALIAS
from interfacy_cli.exceptions import ReservedFlagError, UnsupportedParamError
from interfacy_cli.interfacy_class import InterfacyClass
from interfacy_cli.interfacy_function import InterfacyFunction
from interfacy_cli.interfacy_parameter import (
    CLI_SIMPLE_TYPES,
    EMPTY,
    InterfacyParameter,
    ParameterKind,
    UnionTypeParameter,
)
from interfacy_cli.util import extract_enum_options


def simplify_type(t):
    """
    Simplify type if its not a 'SIMPLE' or 'SPECIAL' type.

    dict[str,str] -> dict
    int | float -> UnionTypeParameter(int,float)
    list[float] -> list[float], since it's CLI_PARSER
    """
    if t in CLI_PARSER.keys() or t in CLI_SIMPLE_TYPES:
        return t
    tp = typing.get_origin(t)
    if type(tp) is types.NoneType:
        return t
    if tp is types.UnionType:
        tp = typing.get_args(t)
        return UnionTypeParameter(tuple(simplify_type(i) for i in tp))
    return simplify_type(tp)


def get_parameter_kind(param: InterfacyParameter) -> ParameterKind:
    if param.type == EMPTY:
        return ParameterKind.BASIC
    if param.type in CLI_SIMPLE_TYPES:
        return ParameterKind.BASIC
    if isinstance(param.type, UnionTypeParameter) or param.type in CLI_PARSER.keys():
        return ParameterKind.SPECIAL
    if type(param.type) in [types.UnionType, UNION_GENERIC_ALIAS]:
        return ParameterKind.UNION
    if type(param.type) in [types.GenericAlias, SPECIAL_GENERIC_ALIAS]:
        return ParameterKind.ALIAS
    return ParameterKind.UNSUPPORTED


def parse_union_param(param: UnionTypeParameter, val: str | Any):
    """
    Try and parse value as every type of an UnionTypeParameter instance
    Return the first one that succedes
    Raises:
        ValueError ... TODO
    """
    parsed_val = EMPTY
    for t in param.params:
        try:
            parsed_val = CLI_PARSER[t](val)
            return parsed_val
        except Exception:
            continue
    raise ValueError(f"{val} can't parsed as any of these types: {param.params}")


class CLI:
    def __init__(
        self,
        func_or_cls,
        class_methods: list | None = None,
        description: str | None = None,
        theme: HelpStringTheme | None = None,
        clear_metavar: bool = True,
    ) -> None:
        """
        Build a command-line interface for a function or class.

        Args:
            func_or_cls:
            class_methods:
            description: Description for the main parser. If not specified, Interfacy will attempt to use the docstring's description.
            theme:
            clear_metavar:
        """
        self.func_or_cls = func_or_cls
        self.class_methods = class_methods
        self.description = description
        self.clear_metavar = clear_metavar
        self.theme = CLI_THEMES.DEFAULT if theme is None else theme
        self.main_parser = argparse.ArgumentParser()
        self.specials: dict[str, dict[str, Any]] = {}  # owner[name][type]

    def run(self):
        if inspect.isclass(self.func_or_cls):  # class
            return self.__build_from_class(self.func_or_cls, self.class_methods)
        else:  # function
            return self.__build_from_function(self.func_or_cls)

    def __build_from_class(self, cls, methods=None):
        cls = InterfacyClass(cls)
        if self.description is None:
            self.main_parser.description = cls.docstring

        subparser = self.main_parser.add_subparsers()
        for method in cls.methods:
            print(method)
            pprint(method.parameters)
            print("_" * 64)

    def make_parser(self, ifunc: InterfacyFunction, parser: argparse.ArgumentParser | None = None):
        """
        Create an ArgumentParser from an InterfacyFunction
        """
        if parser is None:
            parser = argparse.ArgumentParser()
        for param in ifunc.parameters:
            self.add_parameter(parser, param)
        if self.description is None:
            parser.description = self.description
        elif ifunc.has_docstring:
            parser.description = ifunc.description
        return parser

    def __build_from_function(self, func):
        func = InterfacyFunction(func)
        self.specials[func.name] = {}
        parser = self.make_parser(func)
        args = parser.parse_known_args()
        args_dict = args.__dict__

        specials = self.specials[func.name]
        for name, value in args_dict.items():
            if not specials.get(name, False):
                continue
            var_type = specials[name]
            if isinstance(var_type, UnionTypeParameter):
                val = parse_union_param(var_type, value)
                args_dict[name] = val
            if inspect.isclass(var_type) and issubclass(var_type, enum.Enum):
                val = var_type[value]
            else:
                args_dict[name] = CLI_PARSER[var_type](value)
        return func.func(**args_dict)

    def __extra_add_arg_params(self, param: InterfacyParameter):
        """
        Get a dictionary of extra arguments that will be passed to parser.add_argument.
        """
        param_kind = get_parameter_kind(param)
        if param_kind == ParameterKind.UNSUPPORTED:
            raise UnsupportedParamError(param.type)

        extra = {
            "help": param.help_string(self.theme),
            "required": param.is_required,
        }

        if self.clear_metavar:
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

        # Handle enum parameters
        if inspect.isclass(param.type) and issubclass(param.type, enum.Enum):
            self.specials[param.owner][param.name] = param.type
            extra["choices"] = extract_enum_options(param.type)
            extra["type"] = str
            return extra

        # Untyped args
        if not param.is_typed:
            return extra

        if param_kind == ParameterKind.UNION or param_kind == ParameterKind.ALIAS:
            param.type = simplify_type(param.type)
        param_kind = get_parameter_kind(param)

        match param_kind:
            case ParameterKind.UNSUPPORTED:
                raise UnsupportedParamError(param.type)
            case ParameterKind.BASIC:  # Simple types (str, int, float, bool)
                extra["type"] = param.type
            case ParameterKind.SPECIAL:  # Parsable Types (types in CLI_TYPE_PARSER)
                extra["type"] = str
                self.specials[param.owner][param.name] = param.type
            case ParameterKind.ALIAS:  # Alias types like list[str]
                raise ValueError("This should never happen")
            case ParameterKind.UNION:
                raise ValueError("This should never happen")
            case _:
                raise UnsupportedParamError(param.type)

        return extra

    def add_parameter(self, parser: argparse.ArgumentParser, param: InterfacyParameter):
        """
        Add a parameter to an argument parser

        Args:
            parser: ArgumentParser instance
            owner: function or class name the parameter is from
        Raises:
            ReservedFlagError
        """
        if param.name in RESERVED_FLAGS:
            raise ReservedFlagError(param.name)
        extra = self.__extra_add_arg_params(param)
        parser.add_argument(param.flag_name, **extra)


if __name__ == "__main__":
    from interfacy_cli.testing_functions import *

    CLI(test_cls1).run()

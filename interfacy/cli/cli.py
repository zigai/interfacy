import argparse
import enum
import inspect
import types
import typing
from pprint import pp, pprint
from typing import Any

import interfacy.cli.themes as CLI_THEMES
import pretty_errors
from interfacy.cli.parsers import CLI_PARSER
from interfacy.constants import SPECIAL_GENERIC_ALIAS, UNION_GENERIC_ALIAS
from interfacy.exceptions import ReservedFlagError, UnsupportedParamError
from interfacy.interfacy_class import InterfacyClass
from interfacy.interfacy_function import InterfacyFunction
from interfacy.interfacy_parameter import (CLI_SIMPLE_TYPES, EMPTY,
                                           InterfacyParameter, ParameterKind,
                                           UnionTypeParameter)

RESERVED_FLAGS = ["h", "help", "q", "quiet"]


def simplify_type(t):
    """
    Simplify type if its not  'SIMPLE' or 'SPECIAL'
    dict[str,str] -> dict 
    int | float -> (int,float)
    """
    if t in CLI_PARSER.keys() or t in CLI_SIMPLE_TYPES:
        return t
    tp = typing.get_origin(t)
    if type(tp) is types.NoneType:
        return t
    if tp is types.UnionType:
        tp =  typing.get_args(t)
        return UnionTypeParameter(tuple(simplify_type(i) for i in tp))
    return simplify_type(tp)


def get_parameter_kind(param: InterfacyParameter) -> ParameterKind:
    if param.type == EMPTY:
        return ParameterKind.BASIC
    if param.type in CLI_SIMPLE_TYPES:
        return ParameterKind.BASIC
    if isinstance(param.type,UnionTypeParameter) or param.type in CLI_PARSER.keys():
        return ParameterKind.SPECIAL
    if type(param.type) in [types.UnionType, UNION_GENERIC_ALIAS]:
        return ParameterKind.UNION
    if type(param.type) in [types.GenericAlias, SPECIAL_GENERIC_ALIAS]:
        return ParameterKind.ALIAS
    return ParameterKind.UNSUPPORTED


class CLI:

    def __init__(
        self,
        func_or_cls,
        class_methods: list | None = None,
        description: str | None = None,
        theme: dict | None = None,
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
        
        self.specials: dict[str, dict[str,Any]] = {} # owner[name][type]

    def run(self):
        if inspect.isclass(self.func_or_cls):  # class
            return self.__build_from_class(self.func_or_cls, self.class_methods)
        else:  # function
            return self.__build_from_function(self.func_or_cls)

    def __build_from_class(self, cls, methods=None):
        cls = InterfacyClass(cls)
        if self.description is None:
            self.main_parser.description = cls.docstring

        for i in cls.methods:
            print(i)
            pprint(i.parameters)
            print("_" * 64)

    def make_parser(self, ifunc: InterfacyFunction):
        """
        Create an ArgumentParser from an InterfacyFunction
        """
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
        args = parser.parse_args()
        args_dict = args.__dict__
        specials = self.specials[func.name]

        for name, value in args_dict.items():
            if not specials.get(name, False):
                continue
            var_type = specials[name]
            if isinstance(var_type,UnionTypeParameter):
                val = EMPTY
                for t in var_type.params:
                    try:
                        val = CLI_PARSER[t](value)
                    except Exception:
                        continue
                if val == EMPTY:
                    raise ValueError(f"{value} can't parsed as any of these types: {var_type.params}")
                else:
                    args_dict[name] = val
            if issubclass(var_type,enum.Enum):
                val = var_type[value]
            else:
                args_dict[name] = CLI_PARSER[var_type](value)
        func.func(**args_dict)


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

        if inspect.isclass(param.type) and issubclass(param.type,enum.Enum):
            self.specials[param.owner][param.name] = param.type
            extra["choices"] = list(param.type.__members__.keys())
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
            case ParameterKind.SPECIAL: # Parsable Types (types in CLI_TYPE_PARSER)
                extra["type"] = str
                self.specials[param.owner][param.name] = param.type
            case ParameterKind.ALIAS: # Alias types like list[str]
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


if __name__ == '__main__':
    from testing_functions import *
    CLI(test_cls1)

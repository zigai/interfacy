import argparse
import inspect
import json
import os
import sys
from datetime import date

from dateutil import parser as date_parser
from stdl.fs import File, json_load, pickle_load, yaml_load
from stdl.str_util import ColorANSI, str_with_color

from function import InterfacyFunction
from parameter import EMPTY, InterfacyParameter
from testing_functions import *
from util import type_as_str

DEFAULT_CLI_THEME = {"type": ColorANSI.LIGHT_YELLOW, "value": ColorANSI.LIGHT_BLUE}


class CLI():

    def __init__(self, func_or_class, class_methods=None, description=None, theme=None) -> None:
        self.func_or_class = func_or_class
        self.class_methods = class_methods
        self.description = description
        self.parser = argparse.ArgumentParser()
        self.theme = DEFAULT_CLI_THEME if theme is None else theme

    def build(self):
        if inspect.isclass(self.func_or_class):  # class
            return self._build_from_class()
        else:  # function
            return self._build_from_function(self.func_or_class)

    def _build_from_class(self):
        pass

    def _build_from_function(self, func):
        func = InterfacyFunction(func)
        if self.description is None:
            self.parser.description = func.docstr
        for param in func.parameters:
            self._add_param(param)

    def _add_param(self, param: InterfacyParameter):
        param_name = f"--{param.name}"
        required = param.default == EMPTY
        typed = param.type != EMPTY
        help_str = self._get_help_str(param)

    def _get_help_str(self, param: InterfacyParameter):
        if param.is_required and not param.is_typed:
            return ""
        help_str = []
        if param.is_typed:
            help_str.append(f"type: { str_with_color(type_as_str(param.type), self.theme['type'])}")
        if not param.is_required:
            help_str.append(f"default: { str_with_color(param.default,self.theme['value'])}")
        help_str = ", ".join(help_str)
        print(help_str)
        return help_str


if __name__ == '__main__':
    CLI(test_func2).build()

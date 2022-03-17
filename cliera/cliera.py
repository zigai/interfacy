import json
import os
import sys
from argparse import ArgumentParser
from inspect import Parameter, _empty, signature

from stdl.fs import File, json_load, pickle_load, yaml_load
from stdl.str_utils import ANSI_Color, str_colored

if sys.platform == "win32":
    os.system('color')


class Cliera:
    EMPTY = _empty
    SUPPORTED_TYPES = [str, int, float, dict, list, set]
    COMPLEX_TYPES = [dict, list, set, tuple]
    SIMPLE_TYPES = [str, int, float, bool]

    def __init__(self, func) -> None:
        self.parser = ArgumentParser()
        self.func = func
        self.args = signature(self.func)
        self.marked_special = {}
        self.__run()

    def __generate_help_str(self, arg: Parameter):
        arg_type = arg.annotation if arg.annotation != self.EMPTY else ""
        arg_default = arg.default if arg.default != self.EMPTY else ""
        # print(f"{var_type=}, {var_default=}")
        if arg_default == "" and arg_type == "":
            return ""
        if arg_type != "":
            if arg_type is None:
                arg_type = f"type: {str_colored('None',ANSI_Color.LIGHT_YELLOW)}"
            else:
                arg_type = str(arg_type).split("'")[1]
                arg_type = f"type: { str_colored(arg_type,ANSI_Color.LIGHT_YELLOW)}"
        arg_default = "" if arg_default == "" else f"default: {str_colored(arg_default,ANSI_Color.LIGHT_CYAN)}"
        if arg_type != "" and arg_default != "":
            return f"[{arg_type}, {arg_default}]"
        if arg_type != "" and arg_default == "":
            return f"[{arg_type}]"
        return f"[{arg_default}]"

    def __mark_special(self, arg_name: str, arg_type):
        arg_name = arg_name.replace("-", "")
        arg_type = str(arg_type).split("'")[1]
        self.marked_special[arg_name] = arg_type

    def __add_arg(self, arg: Parameter):
        if len(arg.name) == 1:
            var_name = f"-{arg.name}"
        else:
            var_name = f"--{arg.name}"
        help_str = self.__generate_help_str(arg)

        if (arg.default == self.EMPTY and arg.annotation == self.EMPTY):  # Required, No Type Hint
            self.parser.add_argument(var_name, required=True, help=help_str)

        elif (arg.default == self.EMPTY and arg.annotation != self.EMPTY):  # Required, Has Type Hint.
            if arg.annotation is bool:
                self.parser.add_argument(var_name, action="store_true", required=True, help=help_str)
            else:
                if arg.annotation in self.COMPLEX_TYPES:
                    self.__mark_special(var_name, arg.annotation)
                    self.parser.add_argument(var_name, required=True, help=help_str)
                else:
                    self.parser.add_argument(var_name, type=arg.annotation, required=True, help=help_str)

        elif (arg.default != self.EMPTY and arg.annotation == self.EMPTY):  # Optional, No Type Hint.
            self.parser.add_argument(var_name, default=arg.default, required=False, help=help_str)

        elif (arg.default != self.EMPTY and arg.annotation != self.EMPTY):  # Optional. Has Type Hint.
            if arg.annotation in self.COMPLEX_TYPES:
                self.parser.add_argument(var_name, default=arg.default, required=False, help=help_str)
                self.__mark_special(var_name, arg.annotation)
            self.parser.add_argument(var_name, default=arg.default, type=arg.annotation, required=False, help=help_str)
        else:
            raise Exception(f"Unparsable Arguments: {arg}")

    def __parse(self):
        for arg in self.args.parameters.values():
            self.__add_arg(arg)
        args = self.parser.parse_args()
        return args

    def __parse_special_arg(self, value: str, arg_type: str):
        is_file = os.path.exists(value)
        if arg_type in ["list", "set", "tuple"]:
            if is_file:
                # Pickle
                if value.lower().endswith((".pickle", ".pkl")):
                    return pickle_load(value)
                else:
                    # Raw text
                    data = File.splitlines(value)
                    if arg_type == "list":
                        return data
                    elif arg_type == "set":
                        return set(data)
                    elif arg_type == "tuple":
                        return (*data,)
            # Split value to list
            data = value.split(",")
            if arg_type == "list":
                return data
            elif arg_type == "set":
                return set(data)
            elif arg_type == "tuple":
                return (*data,)
        elif arg_type == "dict":
            if is_file:
                # YAML
                if value.lower().endswith((".yaml", ".yml")):
                    return yaml_load(value)
                # Pickle
                elif value.lower().endswith((".pickle", ".pkl")):
                    return pickle_load(value)
                # Json
                return json_load(value)
            # Dict from str
            return json.loads(value)

        raise TypeError(arg_type)

    def __run(self):
        args = self.__parse()
        args_dict = args.__dict__
        for name, value in args_dict.items():
            if name in self.marked_special:
                actual_type = self.marked_special[name]
                # print(f"{name=}, {value=}, {actual_type=}")
                arg_val = self.__parse_special_arg(value, actual_type)
                args_dict[name] = arg_val
        return self.func(**args_dict)

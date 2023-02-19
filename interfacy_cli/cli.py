import argparse
import sys
from argparse import ArgumentParser
from pprint import pp, pprint
from typing import Any, Callable

from nested_argparse import NestedArgumentParser
from objinspect import Class, Function, Method, Parameter, objinspect
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
        shorten_cmd_names: bool = True,
        theme: Theme | None = None,
        run: bool = True,
        print_result: bool = False,
        description: str | None = None,
    ) -> None:
        """
        Args:
            *commands (Callable): The commands to add to the CLI (functions or classes).
            shorten_cmd_names (bool): Whether to shorten command names.
            theme (Theme | None): The theme to use for the CLI help. If None, the default theme will be used.
            run (bool): Whether automaticaly to run the CLI. If False, you will have to call the run method manually.
            print_result (bool): Whether to display the results of the command.
            description (str | None): Override the description of the CLI. If not not provided, the description will be the docstring of the top level command.
        """
        self.commands: list = []
        for i in commands:
            self.commands.append(i)
        self.shorten_command_names = shorten_cmd_names
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
                return self._run_single_func_command(cmd)
            if isinstance(cmd, Class):
                return self._run_single_class_command(cmd)
            raise ValueError(cmd)

        parser = self._get_new_parser()
        parser.epilog = self.theme.get_top_level_epilog(*commands.values())
        subparsers = parser.add_subparsers(dest="command")
        for cmd in commands.values():
            p = subparsers.add_parser(cmd.name, description=cmd.description)
            if isinstance(cmd, (Function, Method)):
                p = self.parser_from_func(cmd, [*RESERVED_FLAGS], p)
            elif isinstance(cmd, Class):
                p = self.parser_from_class(cmd, p)
            else:
                raise TypeError(cmd)
        args = parser.parse_args()
        print(self.get_args())
        print(commands)
        print(args)
        if args.command is None:
            parser.print_help()
            exit(1)
        command = args.command
        obj_args = args.__dict__
        all_args: dict = obj_args[command].__dict__
        del obj_args["command"]
        cmd = commands[command]
        if isinstance(cmd, (Function, Method)):
            for name, value in all_args.items():
                all_args[name] = PARSER.parse(value, cmd.get_param(name).type)
            return cmd.call(**all_args)
        elif isinstance(cmd, Class):
            ...
        else:
            raise TypeError(cmd)

    def run(self) -> Any:
        res = self._run()
        if self.print_result:
            pprint(res)

    def _run_single_func_command(self, func: Function):
        """
        Called when a single function or method is passed to CLI
        """
        ap = self.parser_from_func(func, [*RESERVED_FLAGS])
        if self.description:
            ap.description = self.theme.format_description(self.description)
        args = ap.parse_args(self.get_args())
        args_dict = args.__dict__
        for name, value in args_dict.items():
            args_dict[name] = PARSER.parse(value, func.get_param(name).type)
        return func.call(**args_dict)

    def _run_single_class_command(self, cls: Class):
        """
        Called when a single class is passed to CLI
        """
        parser = self.parser_from_class(cls)
        if self.description:
            parser.description = self.theme.format_description(self.description)
        args = parser.parse_args(self.get_args())
        obj_args = args.__dict__
        if args.command is None:
            parser.print_help()
            exit(1)
        method = args.command
        all_args: dict = obj_args[method].__dict__
        init_func = cls.get_method("__init__")
        init_arg_names = [i.name for i in init_func.params]
        init_args = {k: v for k, v in all_args.items() if k in init_arg_names}
        for name, value in init_args.items():
            init_args[name] = PARSER.parse(value, init_func.get_param(name).type)
        method_args = {k: v for k, v in all_args.items() if k not in init_arg_names}
        command_func = cls.get_method(method)
        for name, value in method_args.items():
            method_args[name] = PARSER.parse(value, command_func.get_param(name).type)
        cls.init(**init_args)
        return cls.call_method(method, **method_args)

    def parser_from_func(
        self, f: Function, taken_names: list[str], parser: ArgumentParser | None = None
    ) -> ArgumentParser:
        """
        Create an ArgumentParser from a Function
        """
        if parser is None:
            parser = self._get_new_parser()
        for param in f.params:
            self.add_parameter(parser, param, taken_names)
        if f.has_docstring:
            parser.description = self.theme.format_description(f.description)
        return parser

    def parser_from_class(self, c: Class, parser: ArgumentParser | None = None):
        """
        Create an ArgumentParser from a Class
        """
        taken_names = [*RESERVED_FLAGS]
        if parser is None:
            parser = self._get_new_parser()
        if c.has_init and not c.is_initialized:
            init = c.get_method("__init__")
        if c.has_docstring:
            parser.description = self.theme.format_description(c.description)
        parser.epilog = self.theme.get_class_commands_epilog(c)  # type: ignore
        cls_methods = c.methods
        subparsers = parser.add_subparsers(dest="command")
        for method in cls_methods:
            if method.name == "__init__":
                continue
            p = subparsers.add_parser(method.name, description=method.description)
            if c.has_init and not c.is_initialized:
                for param in init.params:  # type: ignore
                    self.add_parameter(p, param, taken_names=taken_names)
            p = self.parser_from_func(method, taken_names, p)
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
                cmd_names = (f"-{short_name}".strip(), long_name)

        extra_args = self._extra_add_arg_params(param)
        parser.add_argument(*cmd_names, **extra_args)

    def _extra_add_arg_params(self, param: Parameter) -> dict[str, Any]:
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

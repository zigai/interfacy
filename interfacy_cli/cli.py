import sys
from argparse import ArgumentParser
from pprint import pprint
from typing import Any, Callable

from nested_argparse import NestedArgumentParser
from objinspect import Class, Function, Method, Parameter, objinspect

from interfacy_cli.constants import RESERVED_FLAGS
from interfacy_cli.exceptions import ReservedFlagError, UnsupportedParamError
from interfacy_cli.parser import PARSER
from interfacy_cli.themes import DefaultTheme, Theme

COMMAND_KEY = "command"


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


def parse_args(args: dict, func: Function | Method):
    for name, value in args.items():
        args[name] = PARSER.parse(value, func.get_param(name).type)


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

    def run(self) -> Any:
        res = self._run()
        if self.print_result:
            pprint(res)

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
            command_outer = list(commands.values())[0]
            if isinstance(command_outer, Function):
                return self._run_single_func_command(command_outer)
            if isinstance(command_outer, Class):
                return self._run_single_class_command(command_outer)
            raise ValueError(command_outer)
        return self._run_multi_command(commands)

    def _run_multi_command(self, commands: dict[str, Function | Class]):
        parser = self._get_new_parser()
        parser.epilog = self.theme.get_commands_help(*commands.values())
        subparsers = parser.add_subparsers(dest=COMMAND_KEY, required=True)  # !!!

        for outer_cmd in commands.values():
            subparser = subparsers.add_parser(outer_cmd.name, description=outer_cmd.description)
            if isinstance(outer_cmd, (Function, Method)):
                subparser = self.parser_from_func(outer_cmd, [*RESERVED_FLAGS], subparser)
            elif isinstance(outer_cmd, Class):
                subparser = self.parser_from_class(outer_cmd, subparser)
            else:
                raise TypeError(outer_cmd)

        args = parser.parse_args(self.get_args())
        obj_args = vars(args)
        if COMMAND_KEY not in obj_args:
            parser.print_help()
            exit(1)

        command = obj_args[COMMAND_KEY]
        all_args: dict = vars(obj_args[command])
        del obj_args[COMMAND_KEY]
        cmd_outer = commands[command]

        if isinstance(cmd_outer, (Function, Method)):
            parse_args(all_args, cmd_outer)
            return cmd_outer.call(**all_args)
        elif isinstance(cmd_outer, Class):
            all_args: dict = obj_args[command].__dict__
            if not all_args.get(COMMAND_KEY, False):
                subparsers.choices[command].print_help()
                exit(1)
            inner_cmd_name = all_args[COMMAND_KEY]
            all_args = vars(all_args[COMMAND_KEY])
            cmd_inner = cmd_outer.get_method(inner_cmd_name)

            if not cmd_inner.is_static and cmd_outer.has_init:
                init_func = cmd_outer.get_method("__init__")
                init_arg_names = [i.name for i in init_func.params]
                init_args = {k: v for k, v in all_args.items() if k in init_arg_names}
                parse_args(init_args, init_func)
                method_args = {k: v for k, v in all_args.items() if k not in init_arg_names}
            else:
                init_args = {}
                method_args = all_args
            parse_args(method_args, cmd_inner)

            if cmd_outer.has_init and not cmd_inner.is_static:
                cmd_outer.init(**init_args)
            return cmd_inner.call(**method_args)
        else:
            raise TypeError(cmd_outer)

    def _run_single_func_command(self, func: Function):
        """
        Called when a single function or method is passed to CLI
        """
        ap = self.parser_from_func(func, [*RESERVED_FLAGS])
        if self.description:
            ap.description = self.theme.format_description(self.description)
        args = ap.parse_args(self.get_args())
        args_dict = vars(args)
        parse_args(args_dict, func)
        return func.call(**args_dict)

    def _run_single_class_command(self, cls: Class):
        """
        Called when a single class is passed to CLI
        """
        parser = self.parser_from_class(cls)
        if self.description:
            parser.description = self.theme.format_description(self.description)

        args = parser.parse_args(self.get_args())
        obj_args = vars(args)
        if COMMAND_KEY not in obj_args:
            parser.print_help()
            exit(1)

        method_name = obj_args[COMMAND_KEY]
        all_args: dict = vars(obj_args[method_name])
        method = cls.get_method(method_name)

        if not method.is_static and cls.has_init:
            init_func = cls.get_method("__init__")
            init_arg_names = [i.name for i in init_func.params]
            init_args = {k: v for k, v in all_args.items() if k in init_arg_names}
            parse_args(init_args, init_func)
            method_args = {k: v for k, v in all_args.items() if k not in init_arg_names}
        else:
            init_args = {}
            method_args = all_args

        parse_args(method_args, method)

        if cls.has_init and not method.is_static:
            cls.init(**init_args)
        return method.call(**method_args)

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
        if parser is None:
            parser = self._get_new_parser()
        if c.has_init and not c.is_initialized:
            init = c.get_method("__init__")
        if c.has_docstring:
            parser.description = self.theme.format_description(c.description)
        parser.epilog = self.theme.get_class_commands_help(c)  # type: ignore

        cls_methods = c.methods
        subparsers = parser.add_subparsers(dest=COMMAND_KEY)
        for method in cls_methods:
            if method.name == "__init__":
                continue
            taken_names = [*RESERVED_FLAGS]
            p = subparsers.add_parser(method.name, description=method.description)
            if c.has_init and not c.is_initialized and not method.is_static:
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

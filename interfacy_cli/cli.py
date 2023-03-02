import sys
from argparse import ArgumentParser
from pprint import pprint
from typing import Any, Callable

from nested_argparse import NestedArgumentParser
from objinspect import Class, Function, Method, Parameter, objinspect

from interfacy_cli.constants import RESERVED_FLAGS
from interfacy_cli.exceptions import ReservedFlagError, UnsupportedParamError
from interfacy_cli.themes import DefaultTheme, Theme
from interfacy_cli.type_parser import PARSER
from interfacy_cli.util import get_args, get_command_abbrev

COMMAND_KEY = "command"


def _parse_args(args: dict, func: Function | Method):
    for name, value in args.items():
        args[name] = PARSER.parse(value, func.get_param(name).type)


class CLI:
    def __init__(
        self,
        *commands: Callable,
        add_abbrevs: bool = True,
        theme: Theme | None = None,
        run: bool = True,
        print_result: bool = False,
        description: str | None = None,
        from_file_prefix: str = "@F",
        allow_args_from_file: bool = True,
        install_tab_completion: bool = False,
    ) -> None:
        """
        Args:
            *commands (Callable): The commands to add to the CLI (functions or classes).
            add_abbrevs (bool): Whether to shorten command names.
            theme (Theme | None): The theme to use for the CLI help. If None, the default theme will be used.
            run (bool): Whether automaticaly to run the CLI. If False, you will have to call the run method manually.
            print_result (bool): Whether to display the results of the command.
            description (str | None): Override the description of the CLI. If not not provided, the description will be the docstring of the top level command.
            from_file_prefix (str): The prefix to use for loading arguments from a file.
            allow_args_from_file (bool): Whether to allow loading arguments from a file.
            install_tab_completion (bool): Whether to install tab completion for the CLI.
        """
        self.commands: list = []
        for i in commands:
            self.commands.append(i)
        self.add_abbrevs = add_abbrevs
        self.description = description
        self.theme = theme or DefaultTheme()
        self.print_result = print_result
        self.from_file_prefix = from_file_prefix
        self.allow_args_from_file = allow_args_from_file
        self.install_tab_completion = install_tab_completion
        if run:
            self.run()

    def get_args(self):
        if self.allow_args_from_file:
            return get_args(sys.argv, from_file_prefix=self.from_file_prefix)
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
            command = list(commands.values())[0]
            if isinstance(command, Function):
                return self._run_single_func_command(command)
            if isinstance(command, Class):
                return self._run_single_class_command(command)
            raise ValueError(command)
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
        if self.install_tab_completion:
            self._install_tab_completion(parser)
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
            _parse_args(all_args, cmd_outer)
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
                _parse_args(init_args, init_func)
                method_args = {k: v for k, v in all_args.items() if k not in init_arg_names}
            else:
                init_args = {}
                method_args = all_args
            _parse_args(method_args, cmd_inner)

            if cmd_outer.has_init and not cmd_inner.is_static:
                cmd_outer.init(**init_args)
            return cmd_inner.call(**method_args)
        else:
            raise TypeError(cmd_outer)

    def _run_single_func_command(self, func: Function):
        """
        Called when a single function or method is passed to CLI
        """
        parser = self.parser_from_func(func, [*RESERVED_FLAGS])
        if self.description:
            parser.description = self.theme.format_description(self.description)
        if self.install_tab_completion:
            self._install_tab_completion(parser)
        args = parser.parse_args(self.get_args())
        args_dict = vars(args)
        _parse_args(args_dict, func)
        return func.call(**args_dict)

    def _run_single_class_command(self, cls: Class):
        """
        Called when a single class is passed to CLI
        """
        parser = self.parser_from_class(cls)
        if self.description:
            parser.description = self.theme.format_description(self.description)
        if self.install_tab_completion:
            self._install_tab_completion(parser)
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
            _parse_args(init_args, init_func)
            method_args = {k: v for k, v in all_args.items() if k not in init_arg_names}
        else:
            init_args = {}
            method_args = all_args

        _parse_args(method_args, method)

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
        subparsers = parser.add_subparsers(dest=COMMAND_KEY, required=True)
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
        if self.add_abbrevs:
            short_name = get_command_abbrev(param.name, taken_names)
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

    def _install_tab_completion(self, parser: ArgumentParser):
        import argcomplete

        argcomplete.autocomplete(parser)


__all__ = ["CLI"]

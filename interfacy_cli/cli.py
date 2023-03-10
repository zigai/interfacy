import sys
from argparse import ArgumentParser
from typing import Any, Callable

from nested_argparse import NestedArgumentParser
from objinspect import Class, Function, Method, Parameter, objinspect

from interfacy_cli.constants import COMMAND_KEY, RESERVED_FLAGS, ExitCode
from interfacy_cli.exceptions import (
    DupicateCommandError,
    InterfacyException,
    InvalidCommandError,
    ReservedFlagError,
    UnsupportedParamError,
)
from interfacy_cli.themes import DefaultTheme, Theme
from interfacy_cli.type_parser import PARSER, Parser
from interfacy_cli.util import get_args, get_command_abbrev


def _install_tab_completion(parser: ArgumentParser):
    import argcomplete

    argcomplete.autocomplete(parser)


class CLI:
    def __init__(
        self,
        *commands: Callable,
        run: bool = True,
        add_abbrevs: bool = True,
        theme: Theme | None = None,
        print_result: bool = False,
        description: str | None = None,
        arg_parser: Parser = PARSER,
        allow_args_from_file: bool = True,
        from_file_prefix: str = "@F",
        install_tab_completion: bool = False,
        parser_extensions: dict[Any, Callable] = None,  # type: ignore
    ) -> None:
        """
        Args:
            *commands (Callable): The commands to add to the CLI (functions or classes).
            run (bool): Whether automatically to run the CLI. If False, you will have to call the run method manually.
            add_abbrevs (bool): Whether to shorten command names.
            theme (Theme | None): The theme to use for the CLI help. If None, the default theme will be used.
            print_result (bool): Whether to display the results of the command.
            description (str | None): Override the description of the CLI. If not provided, the description will be the docstring of the top level command.
            arg_parser (Parser): The parser to use for parsing arguments.
            allow_args_from_file (bool): Whether to allow loading arguments from a file.
            from_file_prefix (str): The prefix to use for loading arguments from a file.
            install_tab_completion (bool): Whether to install tab completion for the CLI.
            parser_extensions (dict[Any, Callable]): A dictionary of extensions to add to the parser to support custom types or override existing functionality.
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
        self.arg_parser = arg_parser
        if parser_extensions:
            self.arg_parser.extend(parser_extensions)
        if run:
            self.run()

    def get_args(self):
        if self.allow_args_from_file:
            return get_args(sys.argv, from_file_prefix=self.from_file_prefix)
        return sys.argv[1:]

    def run(self):
        try:
            res = self._run()
            if self.print_result:
                from pprint import pprint

                pprint(res)
        except InterfacyException as e:
            print(f"[interfacy] Error has occurred while building parser: {e}")
            sys.exit(ExitCode.PARSING_ERR)
        except Exception as e:
            print(f"[interfacy] Error has occurred while running command: {e}")
            sys.exit(ExitCode.RUNTIME_ERR)
        sys.exit(ExitCode.SUCCESS)

    def _get_new_parser(self):
        return NestedArgumentParser(formatter_class=self.theme.formatter_class)

    def _collect_commands(self):
        commands: dict[str, Function | Class] = {}
        for i in self.commands:
            c = objinspect(i, inherited=False)
            if c.name in commands:
                raise DupicateCommandError(c.name)
            commands[c.name] = c
        return commands

    def _run(self) -> Any:
        commands = self._collect_commands()
        if len(commands) == 0:
            raise InvalidCommandError("No commands were provided.")
        if len(commands) == 1:
            command = list(commands.values())[0]
            if isinstance(command, Function):
                return self._run_single_func_command(command)
            if isinstance(command, Class):
                return self._run_single_class_command(command)
            raise InvalidCommandError(f"Not a valid command: {command}")
        return self._run_multiple_commands(commands)

    def _run_multiple_commands(self, commands: dict[str, Function | Class]):
        parser = self._get_new_parser()
        parser.epilog = self.theme.get_commands_help(*commands.values())
        subparsers = parser.add_subparsers(dest=COMMAND_KEY, required=True)  # !!!

        for cmd_inner in commands.values():
            sp = subparsers.add_parser(cmd_inner.name, description=cmd_inner.description)
            if isinstance(cmd_inner, (Function, Method)):
                sp = self.parser_from_func(fn=cmd_inner, taken_names=[*RESERVED_FLAGS], parser=sp)
            elif isinstance(cmd_inner, Class):
                sp = self.parser_from_class(cmd_inner, sp)
            else:
                raise InvalidCommandError(f"Not a valid command: {cmd_inner}")

        if self.install_tab_completion:
            _install_tab_completion(parser)

        args = parser.parse_args(self.get_args())
        obj_args = vars(args)
        if COMMAND_KEY not in obj_args:
            parser.print_help()
            sys.exit(ExitCode.INVALID_ARGS)

        command = obj_args[COMMAND_KEY]
        del obj_args[COMMAND_KEY]
        args_all: dict = vars(obj_args[command])
        cmd = commands[command]

        if isinstance(cmd, (Function, Method)):
            self._parse_args(args_all, cmd)
            return cmd.call(**args_all)
        elif isinstance(cmd, Class):
            return self._run_cls(cmd, args_all, parser)
        else:
            raise InvalidCommandError(f"Not a valid command: {cmd}")

    def _run_single_func_command(self, func: Function):
        """
        Called when a single function or method is passed to CLI
        """
        parser = self.parser_from_func(func, [*RESERVED_FLAGS])
        if self.description:
            parser.description = self.theme.format_description(self.description)
        if self.install_tab_completion:
            _install_tab_completion(parser)
        args = parser.parse_args(self.get_args())
        args_dict = vars(args)
        self._parse_args(args_dict, func)
        return func.call(**args_dict)

    def _run_single_class_command(self, cls: Class):
        """
        Called when a single class is passed to CLI
        """
        parser = self.parser_from_class(cls)
        if self.description:
            parser.description = self.theme.format_description(self.description)
        if self.install_tab_completion:
            _install_tab_completion(parser)
        args = parser.parse_args(self.get_args())
        return self._run_cls(cls, vars(args), parser)

    def parser_from_func(
        self, fn: Function, taken_names: list[str], parser: ArgumentParser | None = None
    ) -> ArgumentParser:
        """
        Create an ArgumentParser from a Function
        """
        if parser is None:
            parser = self._get_new_parser()
        for param in fn.params:
            self.add_parameter(parser, param, taken_names)
        if fn.has_docstring:
            parser.description = self.theme.format_description(fn.description)
        return parser

    def parser_from_class(self, cls: Class, parser: ArgumentParser | None = None):
        """
        Create an ArgumentParser from a Class
        """
        if parser is None:
            parser = self._get_new_parser()
        if cls.has_init and not cls.is_initialized:
            init = cls.get_method("__init__")
        if cls.has_docstring:
            parser.description = self.theme.format_description(cls.description)
        parser.epilog = self.theme.get_class_commands_help(cls)  # type: ignore

        subparsers = parser.add_subparsers(dest=COMMAND_KEY, required=True)
        for method in cls.methods:
            if method.name == "__init__":
                continue
            taken_names = [*RESERVED_FLAGS]
            sp = subparsers.add_parser(method.name, description=method.description)
            if cls.has_init and not cls.is_initialized and not method.is_static:
                for param in init.params:  # type: ignore
                    self.add_parameter(sp, param, taken_names=taken_names)
            sp = self.parser_from_func(method, taken_names, sp)
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

        flag_long = f"--{param.name}".strip()
        flags = (flag_long,)
        if self.add_abbrevs:
            if flag_short := get_command_abbrev(param.name, taken_names):
                flags = (f"-{flag_short}".strip(), flag_long)

        extra_args = self._extra_add_arg_params(param)
        parser.add_argument(*flags, **extra_args)

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

    def extend_arg_parser(self, ext: dict[Any, Callable]):
        self.arg_parser.extend(ext)

    def _parse_args(self, args: dict, fn: Function | Method):
        for name, value in args.items():
            args[name] = self.arg_parser.parse(value, fn.get_param(name).type)

    def _split_args(self, args: dict, cls: Class, method: Method):
        if not method.is_static and cls.has_init:
            init_method = cls.get_method("__init__")
            init_arg_names = [i.name for i in init_method.params]
            args_init = {k: v for k, v in args.items() if k in init_arg_names}
            self._parse_args(args_init, init_method)
            args_method = {k: v for k, v in args.items() if k not in init_arg_names}
            self._parse_args(args_method, method)
            return args_init, args_method
        self._parse_args(args, method)
        return {}, args

    def _run_cls(self, cls: Class, args: dict, parser: ArgumentParser):
        if COMMAND_KEY not in args:
            parser.print_help()
            sys.exit(ExitCode.INVALID_ARGS)

        command = args[COMMAND_KEY]
        args_all: dict = vars(args[command])
        method = cls.get_method(command)
        args_init, args_method = self._split_args(args_all, cls, method)

        if cls.has_init and not method.is_static:
            cls.init(**args_init)
        return method.call(**args_method)


__all__ = ["CLI"]

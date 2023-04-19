import sys
from argparse import ArgumentParser
from typing import Any, Callable

import strto
from objinspect import Class, Function, Method, objinspect

from interfacy_cli.argparse_wrappers import SafeRawHelpFormatter
from interfacy_cli.constants import COMMAND_KEY, RESERVED_FLAGS, ExitCode
from interfacy_cli.exceptions import DupicateCommandError, InterfacyException, InvalidCommandError
from interfacy_cli.parser import AutoArgumentParser
from interfacy_cli.themes import InterfacyTheme


def install_tab_completion(parser: ArgumentParser) -> None:
    """Install tab completion for the given parser"""
    try:
        import argcomplete

    except ImportError:
        print(
            "argcomplete not installed. Tab completion not available."
            " Install with 'pip install argcomplete'",
            file=sys.stderr,
        )
        return

    argcomplete.autocomplete(parser)


class CLI(AutoArgumentParser):
    def __init__(
        self,
        *commands: Callable,
        run: bool = True,
        desciption: str | None = None,
        epilog: str | None = None,
        from_file_prefix: str = "@F",
        allow_args_from_file: bool = True,
        type_parser: strto.Parser | None = None,
        parser_extensions: dict[Any, Callable] | None = None,
        formatter_class=SafeRawHelpFormatter,
        read_stdin: bool = False,
        theme: InterfacyTheme | None = None,
        add_abbrevs: bool = True,
        tab_completion: bool = False,
        print_result: bool = False,
    ):
        super().__init__(
            desciption,
            epilog,
            from_file_prefix,
            allow_args_from_file,
            type_parser,
            parser_extensions,  # type: ignore
            formatter_class,
            read_stdin,
            theme,
            add_abbrevs,
        )
        self.commands = commands
        self.tab_completion = tab_completion
        self.print_result = print_result
        if run:
            self.run()

    def install_tab_completion(self, parser) -> None:
        install_tab_completion(parser)

    def run(self) -> None:
        try:
            res = self._run()
            if self.print_result:
                from pprint import pprint

                pprint(res)
        except InterfacyException as e:
            self._log(f"Error has occurred while building parser: {e}")
            sys.exit(ExitCode.PARSING_ERR)
        except Exception as e:
            self._log(f"Error has occurred while running command: {e}")
            sys.exit(ExitCode.RUNTIME_ERR)
        sys.exit(ExitCode.SUCCESS)

    def _print_result(self, res) -> None:
        from pprint import pprint

        pprint(res)

    def _split_args_kwargs(self, args: dict, func: Function | Method) -> tuple[tuple, dict]:
        return (), args  # TODO

    def _split_init_method_args(self, args: dict, cls: Class, method: Method):
        if not method.is_static and cls.has_init:
            init_method = cls.get_method("__init__")
            init_arg_names = [i.name for i in init_method.params]
            args_init = {k: v for k, v in args.items() if k in init_arg_names}
            args_method = {k: v for k, v in args.items() if k not in init_arg_names}
            return args_init, args_method
        return {}, args

    def _collect_commands(self) -> dict[str, Function | Class]:
        commands: dict[str, Function | Class] = {}
        for command in self.commands:
            cmd = objinspect(command, inherited=False)
            if cmd.name in commands:
                raise DupicateCommandError(cmd.name)
            commands[cmd.name] = cmd
        return commands

    def _run(self) -> Any:
        commands = self._collect_commands()
        if len(commands) == 0:
            raise InvalidCommandError("No commands were provided.")
        elif len(commands) == 1:
            command = list(commands.values())[0]
            if isinstance(command, Function):
                return self._run_callable(command)
            elif isinstance(command, Class):
                return self._run_class(command)
            raise InvalidCommandError(f"Not a valid command: {command}")
        return self._run_multi(commands)

    def _run_callable(self, func: Function | Method) -> Any:
        """
        Called when a single function or method is passed to CLI
        """
        parser = self.parser_from_func(func, [*RESERVED_FLAGS])

        if self.description:
            parser.description = self.theme.format_description(self.description)

        if self.tab_completion:
            self.install_tab_completion(parser)

        args = parser.parse_args(self.get_args())
        args_dict = vars(args)
        args, kwargs = self._split_args_kwargs(args_dict, func)
        return func.call(*args, **kwargs)

    def _run_class(self, cls: Class) -> Any:
        """
        Called when a single class is passed to CLI
        """
        parser = self.parser_from_class(cls)

        if self.description:
            parser.description = self.theme.format_description(self.description)

        if self.tab_completion:
            self.install_tab_completion(parser)

        args = parser.parse_args(self.get_args())
        args_dict = vars(args)
        return self._run_class_inner(cls, args_dict, parser)

    def _run_multi(self, commands: dict[str, Function | Class]) -> Any:
        parser = self.parser_from_multi(commands.values())  # type: ignore

        if self.tab_completion:
            self.install_tab_completion(parser)

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
            return cmd.call(**args_all)
        elif isinstance(cmd, Class):
            return self._run_class_inner(cmd, args_all, parser)
        else:
            raise InvalidCommandError(f"Not a valid command: {cmd}")

    def _run_class_inner(self, cls: Class, args: dict, parser: ArgumentParser):
        if COMMAND_KEY not in args:
            parser.print_help()
            sys.exit(ExitCode.INVALID_ARGS)

        command = args[COMMAND_KEY]
        args_all: dict = vars(args[command])
        method = cls.get_method(command)
        args_init, args_method = self._split_init_method_args(args_all, cls, method)

        if cls.has_init and not method.is_static:
            init_args, init_kwargs = self._split_args_kwargs(args_init, cls.get_method("__init__"))
            cls.init(*init_args, **init_kwargs)

        method_args, method_kwargs = self._split_args_kwargs(args_method, method)
        return cls.call_method(command, *method_args, **method_kwargs)


__all__ = ["CLI"]

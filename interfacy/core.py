import sys
from abc import abstractmethod
from enum import IntEnum, auto
from typing import Any, Callable

from objinspect import Class, Function, Method
from objinspect.typing import type_args, type_name, type_origin
from stdl.fs import read_piped
from stdl.st import colored, terminal_link
from strto import StrToTypeParser, get_parser

from interfacy.exceptions import InvalidCommandError
from interfacy.flag_generator import BasicFlagGenerator, FlagGenerator
from interfacy.themes import ParserTheme
from interfacy.util import AbbrevationGenerator, DefaultAbbrevationGenerator


class ExitCode(IntEnum):
    SUCCESS = 0
    ERR_INVALID_ARGS = auto()
    ERR_PARSING = auto()
    ERR_RUNTIME = auto()
    ERR_RUNTIME_INTERNAL = auto()


class InterfacyParserCore:
    method_skips: list[str] = ["__init__", "__repr__", "repr"]
    logger_message_tag: str = "interfacy"
    RESERVED_FLAGS: list[str] = []

    def __init__(
        self,
        description: str | None = None,
        epilog: str | None = None,
        theme: ParserTheme | None = None,
        type_parser: StrToTypeParser | None = None,
        *,
        run: bool = False,
        print_result: bool = False,
        tab_completion: bool = False,
        full_error_traceback: bool = False,
        allow_args_from_file: bool = True,
        sys_exit_enabled: bool = True,
        flag_strategy: FlagGenerator = BasicFlagGenerator(),
        abbrevation_gen: AbbrevationGenerator = DefaultAbbrevationGenerator(),
        pipe_target: dict[str, str] | None = None,
        print_result_func: Callable = print,
    ) -> None:
        self.epilog = epilog
        self.theme = theme or ParserTheme()
        self.autorun = run
        self.description = description
        self.type_parser = type_parser or get_parser(from_file=allow_args_from_file)

        self.allow_args_from_file = allow_args_from_file
        self.enable_tab_completion = tab_completion
        self.display_result = print_result
        self.full_error_traceback = full_error_traceback
        self.sys_exit_enabled = sys_exit_enabled

        self.abbrevation_gen = abbrevation_gen
        self.flag_strategy = flag_strategy
        self.pipe_target = pipe_target
        self.result_display_fn = print_result_func

        self.theme.flag_generator = self.flag_strategy
        self.commands: dict[str, Function | Class | Method] = {}
        if self.pipe_target:
            self.piped = read_piped()
        else:
            self.piped = None

    def get_args(self) -> list[str]:
        return sys.argv[1:]

    def exit(self, code: ExitCode):
        if self.sys_exit_enabled:
            sys.exit(code)

    def parse_args(self, args: list[str] | None = None) -> dict[str, Any]:
        raise NotImplementedError

    def parser_from_command(self, command: Function | Method | Class, main: bool = False):
        if isinstance(command, (Function, Method)):
            return self.parser_from_function(command, taken_flags=[*self.RESERVED_FLAGS])
        if isinstance(command, Class):
            return self.parser_from_class(command)
        raise InvalidCommandError(command)

    def _should_skip_method(self, method: Method) -> bool:
        return method.name.startswith("_")

    def log(self, message: str) -> None:
        print(f"[{self.logger_message_tag}] {message}", file=sys.stdout)

    def log_error(self, message: str) -> None:
        message = f"[{self.logger_message_tag}] {message}"
        message = colored(message, color="red")
        print(message, file=sys.stderr)

    def log_exception(self, e: Exception) -> None:
        import sys
        import traceback

        if self.full_error_traceback:
            print(traceback.format_exc(), file=sys.stderr)

        message = ""
        tb = e.__traceback__

        exception_str = type_name(str(type(e))) + ": " + str(e)
        file_info = None
        if tb:
            file_info = f"{terminal_link(tb.tb_frame.f_code.co_filename)}:{tb.tb_lineno}"
        if file_info:
            message += file_info
            message += " "

        message += f"{colored(exception_str,color='red')}"
        message = f"[{self.logger_message_tag}] {message}"
        message = colored(message, color="red")
        print(message, file=sys.stderr)

    def add_command(self, command: Callable, name: str | None = None):
        raise NotImplementedError

    def run(self, *commands: Callable, args: list[str] | None = None) -> Any:
        raise NotImplementedError

    @abstractmethod
    def parser_from_function(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def parser_from_class(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def parser_from_multiple_commands(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def install_tab_completion(self, *args, **kwargs) -> None:
        raise NotImplementedError


__all__ = ["InterfacyParserCore", "ExitCode"]

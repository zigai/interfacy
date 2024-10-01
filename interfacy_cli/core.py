import sys
import typing as T
from enum import IntEnum, auto

from objinspect import Class, Function, Method
from stdl.fs import read_piped
from stdl.st import colored
from strto import StrToTypeParser, get_parser

from interfacy_cli.exceptions import InvalidCommandError
from interfacy_cli.flag_generator import BasicFlagGenerator, FlagGenerator
from interfacy_cli.themes import InterfacyTheme
from interfacy_cli.util import AbbrevationGenerator, DefaultAbbrevationGenerator, show_result


class ExitCode(IntEnum):
    SUCCESS = auto()
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
        theme: InterfacyTheme | None = None,
        type_parser: StrToTypeParser | None = None,
        *,
        run: bool = False,
        allow_args_from_file: bool = True,
        flag_strategy: FlagGenerator = BasicFlagGenerator(),
        abbrevation_gen: AbbrevationGenerator = DefaultAbbrevationGenerator(),
        pipe_target: dict[str, str] | None = None,
        tab_completion: bool = False,
        print_result: bool = False,
        print_result_func: T.Callable = show_result,
        full_error_traceback: bool = False,
        disable_sys_exit: bool = False,
    ) -> None:
        self.type_parser = type_parser or get_parser(from_file=allow_args_from_file)
        self.autorun = run
        self.allow_args_from_file = allow_args_from_file
        self.description = description
        self.epilog = epilog
        self.pipe_target = pipe_target
        self.enable_tab_completion = tab_completion
        self.result_display_fn = print_result_func
        self.display_result = print_result
        self.theme = theme or InterfacyTheme()
        self.flag_strategy = flag_strategy
        self.abbrevation_gen = abbrevation_gen
        self.full_error_traceback = full_error_traceback
        self.disable_sys_exit = disable_sys_exit
        self.theme.translate_name = self.flag_strategy.argument_translator.translate
        self.commands: dict[str, Function | Class | Method] = {}
        if self.pipe_target:
            self.piped = read_piped()
        else:
            self.piped = None

    def get_args(self) -> list[str]:
        return sys.argv[1:]

    def log(self, message: str) -> None:
        print(f"[{self.logger_message_tag}] {message}", file=sys.stdout)

    def log_err(self, message: str) -> None:
        message = f"[{self.logger_message_tag}] {message}"
        message = colored(message, color="red")
        print(message, file=sys.stderr)

    def exit(self, code: ExitCode):
        if self.disable_sys_exit:
            return
        sys.exit(code)

    def parser_from_command(self, command: Function | Method | Class, main: bool = False):
        if isinstance(command, (Function, Method)):
            return self.parser_from_function(command, taken_flags=[*self.RESERVED_FLAGS])
        if isinstance(command, Class):
            return self.parser_from_class(command)
        raise InvalidCommandError(command)

    def _should_skip_method(self, method: Method) -> bool:
        return method.name.startswith("_")

    def parser_from_function(
        self,
        function: Function | Method,
        taken_flags: list[str] | None = None,
    ):
        raise NotImplementedError

    def parser_from_class(self, cls: Class, parser=None):
        raise NotImplementedError

    def parser_from_multiple_commands(self, commands: list[Function | Class]):
        raise NotImplementedError

    def add_command(self, command: T.Callable, name: str | None = None):
        raise NotImplementedError

    def install_tab_completion(self, parser) -> None:
        raise NotImplementedError

    def run(self, *commands: T.Callable, args: list[str] | None = None) -> T.Any:
        raise NotImplementedError


__all__ = ["InterfacyParserCore", "ExitCode"]

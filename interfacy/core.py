import sys
from abc import abstractmethod
from collections.abc import Callable, Sequence
from enum import IntEnum, auto
from typing import Any, ClassVar

from objinspect import Class, Function, Method, inspect
from objinspect.typing import type_name
from stdl.st import colored, terminal_link
from strto import StrToTypeParser, get_parser

from interfacy.command import Command
from interfacy.exceptions import DuplicateCommandError, InvalidCommandError
from interfacy.logger import get_logger
from interfacy.naming import (
    AbbreviationGenerator,
    CommandNameRegistry,
    DefaultAbbreviationGenerator,
    DefaultFlagStrategy,
    FlagStrategy,
)
from interfacy.themes import ParserTheme

logger = get_logger(__name__)


class ExitCode(IntEnum):
    SUCCESS = 0
    ERR_INVALID_ARGS = auto()
    ERR_PARSING = auto()
    ERR_RUNTIME = auto()
    ERR_RUNTIME_INTERNAL = auto()


class InterfacyParser:
    RESERVED_FLAGS: ClassVar[list[str]] = []
    logger_message_tag: str = "interfacy"

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
        flag_strategy: FlagStrategy | None = None,
        abbreviation_gen: AbbreviationGenerator | None = None,
        pipe_target: dict[str, str] | None = None,
        print_result_func: Callable = print,
    ) -> None:
        self.description = description
        self.epilog = epilog
        self.method_skips: list[str] = ["__init__", "__repr__", "repr"]
        self.pipe_target = pipe_target
        self.result_display_fn = print_result_func

        self.autorun = run
        self.allow_args_from_file = allow_args_from_file
        self.full_error_traceback = full_error_traceback
        self.enable_tab_completion = tab_completion
        self.sys_exit_enabled = sys_exit_enabled
        self.display_result = print_result

        self.abbreviation_gen = abbreviation_gen or DefaultAbbreviationGenerator()
        self.type_parser = type_parser or get_parser(from_file=allow_args_from_file)
        self.flag_strategy = flag_strategy or DefaultFlagStrategy()
        self.theme = theme or ParserTheme()
        self.theme.flag_generator = self.flag_strategy
        self.name_registry = CommandNameRegistry(self.flag_strategy.command_translator)
        self.theme.name_registry = self.name_registry

        self.commands: dict[str, Command] = {}

    def add_command(
        self,
        command: Callable | Any,
        name: str | None = None,
        description: str | None = None,
        aliases: Sequence[str] | None = None,
    ) -> Command:
        obj = inspect(command, inherited=False)

        canonical_name, command_aliases = self.name_registry.register(
            default_name=obj.name,
            explicit_name=name,
            aliases=aliases,
        )

        if canonical_name in self.commands:
            raise DuplicateCommandError(canonical_name)

        cmd = Command(
            obj=obj,
            name=canonical_name,
            description=description,
            aliases=command_aliases,
        )
        self.commands[canonical_name] = cmd
        logger.debug(f"Added command: {cmd}")
        return cmd

    def get_commands(self) -> list[Command]:
        return list(self.commands.values())

    def get_command_by_cli_name(self, cli_name: str) -> Command:
        canonical = self.name_registry.canonical_for(cli_name)
        if canonical is None:
            raise InvalidCommandError(cli_name)
        return self.commands[canonical]

    def get_args(self) -> list[str]:
        return sys.argv[1:]

    def exit(self, code: ExitCode) -> ExitCode:
        logger.info(f"Exit code: {code}")
        if self.sys_exit_enabled:
            sys.exit(code)
        return code

    def parser_from_command(self, command: Function | Method | Class, main: bool = False):
        if isinstance(command, (Function, Method)):
            return self.parser_from_function(command, taken_flags=[*self.RESERVED_FLAGS])
        if isinstance(command, Class):
            return self.parser_from_class(command)
        raise InvalidCommandError(command)

    def _should_skip_method(self, method: Method) -> bool:
        return method.name.startswith("_")

    def parse_args(self, args: list[str] | None = None) -> dict[str, Any]:
        raise NotImplementedError

    def run(self, *commands: Callable, args: list[str] | None = None) -> Any:
        raise NotImplementedError

    @abstractmethod
    def parser_from_function(self, *args, **kwargs): ...

    @abstractmethod
    def parser_from_class(self, *args, **kwargs): ...

    @abstractmethod
    def parser_from_multiple_commands(self, *args, **kwargs): ...

    @abstractmethod
    def install_tab_completion(self, *args, **kwargs) -> None: ...

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
        if tb:
            file_info = f"{terminal_link(tb.tb_frame.f_code.co_filename)}:{tb.tb_lineno}"
            message += file_info
            message += " "

        message += f"{colored(exception_str, color='red')}"
        message = f"[{self.logger_message_tag}] {message}"
        message = colored(message, color="red")
        print(message, file=sys.stderr)


__all__ = ["InterfacyParser", "ExitCode"]

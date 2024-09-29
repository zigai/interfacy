import sys
import typing as T

from objinspect import Class, Function, Method, Parameter, inspect
from objinspect.typing import is_generic_alias, type_args, type_name, type_origin
from stdl.fs import read_piped
from stdl.st import kebab_case, snake_case
from strto import StrToTypeParser, get_parser
from strto.parsers import Parser

from interfacy_cli.exceptions import DuplicateCommandError, InvalidCommandError
from interfacy_cli.themes import InterfacyTheme
from interfacy_cli.util import (
    AbbrevationGenerator,
    DefaultAbbrevationGenerator,
    TranslationMapper,
    is_list_or_list_alias,
)


def show_result(result: T.Any, handler=print):
    if isinstance(result, list):
        for i in result:
            handler(i)
    elif isinstance(result, dict):
        from pprint import pprint

        pprint(result)
    else:
        handler(result)


class ExitCode:
    SUCCESS = 0
    INVALID_ARGS_ERR = 1
    RUNTIME_ERR = 2
    PARSING_ERR = 3


FlagsStyle = T.Literal["keyword_only", "required_positional"]


class FlagStrategy(T.Protocol):
    arg_translator: TranslationMapper
    command_translator: TranslationMapper
    style: FlagsStyle

    def get_arg_flags(
        self,
        name: str,
        param: Parameter,
        taken_flags: list[str],
        abbrev_gen: AbbrevationGenerator,
    ) -> tuple[str, ...]: ...


class BasicFlagStrategy(FlagStrategy):
    flag_translate_fn = {"none": lambda s: s, "kebab": kebab_case, "snake": snake_case}

    def __init__(
        self,
        style: FlagsStyle = "required_positional",
        translation_mode: T.Literal["none", "kebab", "snake"] = "kebab",
    ) -> None:
        self.style = style
        self.translation_mode = translation_mode
        self.arg_translator = self._get_flag_translator()
        self.command_translator = self._get_flag_translator()
        self._nargs_list_count = 0

    def _get_flag_translator(self) -> TranslationMapper:
        if self.translation_mode not in self.flag_translate_fn:
            raise ValueError(
                f"Invalid flag translation mode: {self.translation_mode}. "
                f"Valid modes are: {', '.join(self.flag_translate_fn.keys())}"
            )
        return TranslationMapper(self.flag_translate_fn[self.translation_mode])

    def get_arg_flags(
        self,
        name: str,
        param: Parameter,
        taken_flags: list[str],
        abbrev_gen: AbbrevationGenerator,
    ) -> tuple[str, ...]:
        """
        Generate CLI flag names for a given parameter based on its name and already taken flags.

        Args:
            param_name (str): The name of the parameter for which to generate flags.
            taken_flags (list[str]): A list of flags that are already in use.

        Returns:
            tuple[str, ...]: A tuple containing the long flag (and short flag if applicable).
        """
        is_bool_flag = param.is_typed and param.type is bool
        is_positional_list = (
            is_list_or_list_alias(param.type)
            and param.is_required
            and self.style == "required_positional"
        )

        # Return positional argument?
        if is_positional_list and self._nargs_list_count < 1:
            self._nargs_list_count += 1
            return (name,)
        if (
            not is_bool_flag
            and not is_positional_list
            and param.is_required
            and self.style == "required_positional"
        ):
            return (name,)

        if len(name) == 1:
            flag_long = f"-{name}".strip()
        else:
            flag_long = f"--{name}".strip()

        flags = (flag_long,)
        if is_bool_flag:
            return flags

        if flag_short := abbrev_gen.generate(name, taken_flags):
            flag_short = flag_short.strip()
            if flag_short != name:
                flags = (f"-{flag_short}", flag_long)
        return flags


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
        flag_strategy: FlagStrategy = BasicFlagStrategy(),
        abbrev_gen: AbbrevationGenerator = DefaultAbbrevationGenerator(),
        pipe_target: dict[str, str] | None = None,
        tab_completion: bool = False,
        print_result: bool = False,
        print_result_func: T.Callable = show_result,
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
        self.abbrev_gen = abbrev_gen
        self.theme.translate_name = self.flag_strategy.arg_translator.translate
        self.commands: dict[str, Function | Class | Method] = {}
        if self.pipe_target:
            self.piped = read_piped()
        else:
            self.piped = None

    def get_args(self) -> list[str]:
        return sys.argv[1:]

    def log(self, message: str) -> None:
        print(f"[{self.logger_message_tag}] {message}", file=sys.stdout)

    def parser_from_command(self, command: Function | Method | Class, main: bool = False):
        if isinstance(command, (Function, Method)):
            return self.parser_from_function(command, taken_flags=[*self.RESERVED_FLAGS])
        if isinstance(command, Class):
            return self.parser_from_class(command)
        raise InvalidCommandError(f"Not a valid command: {command}")

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


__all__ = [
    "InterfacyParserCore",
    "FlagsStyle",
    "FlagStrategy",
    "BasicFlagStrategy",
    "ExitCode",
]

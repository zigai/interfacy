import sys
import typing as T
from argparse import ArgumentParser
from enum import Enum
from typing import Literal

import strto
from objinspect import Class, Function, Method, Parameter
from stdl import fs
from stdl.st import kebab_case, snake_case

from interfacy_cli.themes import InterfacyTheme
from interfacy_cli.util import Translator, get_abbrevation


class FlagsStrategy:
    """
    Enum to specify how flags should be handled when generating a CLI from a function.

    Attributes:
        ALL_KEYWORD_ONLY: All parameters are keyword-only and flags are generated from the parameter names.
        REQUIRED_POSITIONAL: All required parameters are positional and all optional parameters are keyword-only.
    """

    KEYWORD_ONLY = "keyword_only"
    REQUIRED_POSITIONAL = "required_positional"


class AutoParserCore:
    method_skips = ["__init__"]
    log_msg_tag = "interfacy"
    flag_translate_fn = {"none": lambda s: s, "kebab": kebab_case, "snake": snake_case}
    output_sink = sys.stdout.write

    def __init__(
        self,
        desciption: str | None = None,
        epilog: str | None = None,
        theme: InterfacyTheme | None = None,
        value_parser: strto.Parser | None = None,
        *,
        flag_strategy: T.Literal["keyword_only", "required_positinal"] = "required_positinal",
        flag_translation_mode: Literal["none", "kebab", "snake"] = "kebab",
        from_file_prefix: str = "@F",
        display_result: bool = True,
        add_abbrevs: bool = True,
        read_stdin: bool = False,
        allow_args_from_file: bool = True,
    ) -> None:
        self.desciption = desciption
        self.epilog = epilog
        self.flag_strategy = flag_strategy
        self.from_file_prefix = from_file_prefix
        self.allow_args_from_file = allow_args_from_file
        self.read_stdin = read_stdin
        self.add_abbrevs = add_abbrevs
        self.display_result = display_result
        self.flag_translation_mode = flag_translation_mode
        self.value_parser = value_parser or strto.get_parser()
        self.theme = theme or InterfacyTheme()
        self.stdin = fs.read_stdin() if self.read_stdin else None
        self.flag_translator = Translator(self.flag_translate_fn[flag_translation_mode])
        self.name_translator = self.flag_translator.get_translation
        self.theme.name_translator = self.name_translator

    def _log(self, msg: str) -> None:
        print(f"[{self.log_msg_tag}] {msg}")

    def _display_result(self, value: T.Any) -> None:
        print(value)

    def _get_arg_flags(
        self,
        param_name: str,
        param: Parameter,
        taken_flags: list[str],
    ) -> tuple[str, ...]:
        """
        Generate CLI flag names for a given parameter based on its name and already taken flags.

        Args:
            param_name (str): The name of the parameter for which to generate flags.
            taken_flags (list[str]): A list of flags that are already in use.

        Returns:
            tuple[str, ...]: A tuple containing the long flag (and short flag if applicable).
        """

        if self.flag_strategy == FlagsStrategy.REQUIRED_POSITIONAL and param.is_required:
            return (param_name,)

        if len(param_name) == 1:
            flag_long = f"-{param_name}".strip()
        else:
            flag_long = f"--{param_name}".strip()

        flags = (flag_long,)
        if self.add_abbrevs:
            if flag_short := get_abbrevation(param_name, taken_flags):
                flags = (f"-{flag_short}".strip(), flag_long)
        return flags

    def set_description(self, description: str | None = None) -> None:
        raise NotImplementedError

    def set_epilog(self, epilog: str | None = None) -> None:
        raise NotImplementedError

    def add_parameter(self, parser, param: Parameter, taken_flags: list[str]) -> None:
        raise NotImplementedError

    def parser_from_method(
        self,
        method: Method,
        taken_flags: list[str],
        parser: ArgumentParser | None = None,
    ):
        raise NotImplementedError

    def parser_from_func(self, fn: Function, taken_flags: list[str] | None = None, parser=None):
        raise NotImplementedError

    def parser_from_class(self, cls: Class, parser=None):
        raise NotImplementedError

    def parser_from_multiple(self, commands: list[Function | Class]):
        raise NotImplementedError


__all__ = ["AutoParserCore", "FlagsStrategy"]

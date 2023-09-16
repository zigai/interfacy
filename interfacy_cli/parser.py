import sys
from argparse import ArgumentParser
from enum import Enum
from functools import partial
from typing import Any, Callable, Literal

import strto
from nested_argparse import NestedArgumentParser
from objinspect import Class, Function, Method, Parameter, objinspect
from stdl import fs
from stdl.st import kebab_case, snake_case
from strto.converters import Converter

from interfacy_cli.argparse_wrappers import ArgumentParserWrapper, SafeRawHelpFormatter
from interfacy_cli.constants import COMMAND_KEY, RESERVED_FLAGS
from interfacy_cli.exceptions import InvalidCommandError, ReservedFlagError
from interfacy_cli.themes import InterfacyTheme
from interfacy_cli.util import Translator, get_abbrevation, get_args


class FlagsStrategy(Enum):
    """
    Enum to specify how flags should be handled when generating a CLI from a function.

    Attributes:
        ALL_KEYWORD_ONLY: All parameters are keyword-only and flags are generated from the parameter names.
        REQUIRED_POSITIONAL: All required parameters are positional and all optional parameters are keyword-only.
    """

    ALL_KEYWORD_ONLY = "keyword_only"
    REQUIRED_POSITIONAL = "required_positional"


class InterfacyArgumentParser:
    def __init__(
        self,
        desciption: str | None = None,
        epilog: str | None = None,
        from_file_prefix: str = "@F",
        allow_args_from_file: bool = True,
        type_parser: strto.Parser | None = None,
        parser_extensions: dict[Any, Callable] = None,  # type: ignore
        formatter_class=SafeRawHelpFormatter,
        flag_strategy: FlagsStrategy = FlagsStrategy.REQUIRED_POSITIONAL,
    ) -> None:
        self.from_file_prefix = from_file_prefix
        self.allow_args_from_file = allow_args_from_file
        self.type_parser = type_parser or strto.get_parser()
        self.formatter_class = formatter_class
        self.flag_strategy = flag_strategy
        if parser_extensions:
            self.type_parser.extend(parser_extensions)  # type: ignore
        self.parser_extensions = parser_extensions or {}
        self._main_parser = self._new_parser()
        self.set_description(desciption)
        self.set_epilog(epilog)

    @property
    def description(self) -> str | None:
        return self._main_parser.description

    @property
    def epilog(self) -> str | None:
        return self._main_parser.epilog

    @property
    def parser(self) -> NestedArgumentParser:
        return self._main_parser

    def _new_parser(self):
        return ArgumentParserWrapper(formatter_class=self.formatter_class)

    def set_description(self, description: str | None = None) -> None:
        self._main_parser.description = description

    def set_epilog(self, epilog: str | None = None) -> None:
        self._main_parser.epilog = epilog

    def add_argument(self, *args, **kwargs):
        if "type" in kwargs:
            func = partial(self.type_parser.parse, t=kwargs["type"])
            kwargs["type"] = func
        return self._main_parser.add_argument(*args, **kwargs)

    def parse_args(self, args: list[str] | None = None):
        if args is None:
            args = self.get_args()
        return self._main_parser.parse_args(args)

    def add_subparsers(self, *args, **kwargs):
        return self._main_parser.add_subparsers(*args, **kwargs)

    def get_args(self) -> list[str]:
        if self.allow_args_from_file:
            return get_args(sys.argv, from_file_prefix=self.from_file_prefix)
        return sys.argv[1:]


class AutoArgparseParser(InterfacyArgumentParser):
    flag_translate_fn = {"none": lambda s: s, "kebab": kebab_case, "snake": snake_case}
    method_skips = ["__init__"]
    log_msg_tag = "interfacy"

    def __init__(
        self,
        desciption: str | None = None,
        epilog: str | None = None,
        from_file_prefix: str = "@F",
        allow_args_from_file: bool = True,
        type_parser: strto.Parser | None = None,
        parser_extensions: dict[Any, Callable] = None,  # type: ignore
        formatter_class=SafeRawHelpFormatter,
        read_stdin: bool = False,
        theme: InterfacyTheme | None = None,
        add_abbrevs: bool = True,
        flag_translation_mode: Literal["none", "kebab", "snake"] = "kebab",
    ):
        super().__init__(
            desciption=desciption,
            epilog=epilog,
            from_file_prefix=from_file_prefix,
            allow_args_from_file=allow_args_from_file,
            type_parser=type_parser,
            formatter_class=formatter_class,
            parser_extensions=parser_extensions,
        )
        self.theme = theme or InterfacyTheme()
        self.flag_translator = Translator(self.flag_translate_fn[flag_translation_mode])
        self.name_translator = partial(self.flag_translator.get_translation)
        self.theme.name_translator = self.name_translator
        self.read_stdin = read_stdin
        self.stdin = fs.read_stdin() if self.read_stdin else None
        self.add_abbrevs = add_abbrevs

    def _log(self, msg: str) -> None:
        print(f"[{self.log_msg_tag}] {msg}", file=sys.stdout)

    def add_parameter(
        self,
        parser: ArgumentParser,
        param: Parameter,
        taken_flags: list[str],
    ):
        if param.name in taken_flags:
            raise ReservedFlagError(param.name)
        name = self.name_translator(param.name)
        flags = self._get_arg_flags(name, param, taken_flags)
        extra_args = self._extra_add_arg_params(param)
        return parser.add_argument(*flags, **extra_args)

    def parser_from_func(
        self,
        fn: Function,
        taken_flags: list[str] | None = None,
        parser: ArgumentParser | None = None,
    ) -> ArgumentParser:
        """
        Create an ArgumentParser from a Function
        """
        if taken_flags is None:
            taken_flags = []
        if parser is None:
            parser = self._new_parser()
        for param in fn.params:
            self.add_parameter(parser, param, taken_flags)
        if fn.has_docstring:
            parser.description = self.theme.format_description(fn.description)
        return parser

    def parser_from_method(
        self,
        method: Method,
        taken_flags: list[str],
        parser: ArgumentParser | None = None,
    ) -> ArgumentParser:
        """
        Create an ArgumentParser from a Method
        """
        if parser is None:
            parser = self._new_parser()
        for param in method.params:
            self.add_parameter(parser, param, taken_flags)

        if method.has_docstring:
            parser.description = self.theme.format_description(method.description)

        obj_class = Class(method.cls)

        init = obj_class.init_method
        if init is None:
            return parser

        for param in init.params:
            self.add_parameter(parser, param, taken_flags)
        return parser

    def parser_from_class(
        self,
        cls: Class,
        parser: ArgumentParser | None = None,
    ) -> ArgumentParser:
        """
        Create an ArgumentParser from a Class
        """
        if parser is None:
            parser = self._new_parser()
        if cls.has_init and not cls.is_initialized:
            init = cls.get_method("__init__")
        if cls.has_docstring:
            parser.description = self.theme.format_description(cls.description)

        parser.epilog = self.theme.get_commands_help_class(cls)  # type: ignore

        subparsers = parser.add_subparsers(dest=COMMAND_KEY, required=True)
        for method in cls.methods:
            if method.name in self.method_skips:
                continue
            taken_flags = [*RESERVED_FLAGS]
            method_name = self.name_translator(method.name)

            sp = subparsers.add_parser(method_name, description=method.description)
            if cls.has_init and not cls.is_initialized and not method.is_static:
                for param in init.params:  # type: ignore
                    self.add_parameter(sp, param, taken_flags=taken_flags)
            sp = self.parser_from_func(method, taken_flags, sp)
        return parser

    def parser_from_multiple(
        self,
        commands: list[Function | Class],
    ) -> ArgumentParser:
        parser = self._new_parser()
        parser.epilog = self.theme.get_commands_help_multiple(commands)
        subparsers = parser.add_subparsers(dest=COMMAND_KEY, required=True)

        for cmd in commands:
            command_name = self.name_translator(cmd.name)
            sp = subparsers.add_parser(command_name, description=cmd.description)
            if isinstance(cmd, Function):
                sp = self.parser_from_func(fn=cmd, taken_flags=[*RESERVED_FLAGS], parser=sp)
            elif isinstance(cmd, Class):
                sp = self.parser_from_class(cmd, sp)
            elif isinstance(cmd, Method):
                sp = self.parser_from_method(cmd, sp)
            else:
                raise InvalidCommandError(f"Not a valid command: {cmd}")
        return parser

    def extend_type_parser(self, ext: dict[Any, Converter]):
        self.type_parser.extend(ext)

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

    def _extra_add_arg_params(self, param: Parameter) -> dict[str, Any]:
        """
        This method creates a dictionary with additional argument parameters needed to
        customize argparse's `add_argument` method based on a given `Parameter` object.

        Args:
            param (Parameter): The parameter for which to construct additional parameters.

        Returns:
            dict[str, Any]: A dictionary containing additional parameter settings like "help",
            "required", "metavar", and "default".

        """
        extra = {"help": self.theme.get_parameter_help(param)}

        if self.theme.clear_metavar:
            extra["metavar"] = "\b"

        if self.flag_strategy == FlagsStrategy.REQUIRED_POSITIONAL:
            if not param.is_required:
                extra["required"] = param.is_required  # type:ignore
            else:
                del extra["metavar"]
        else:
            extra["required"] = param.is_required  # type:ignore

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


__all__ = ["InterfacyArgumentParser", "AutoArgparseParser"]

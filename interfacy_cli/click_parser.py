import re
import sys
import typing as T
from gettext import gettext as _
from os import get_terminal_size

import click
from click import argument, pass_context
from click.exceptions import MissingParameter, UsageError, _join_param_hints
from objinspect import Class, Function, Method, Parameter, inspect
from stdl.fs import read_piped
from strto import StrToTypeParser

from interfacy_cli.core import DefaultFlagStrategy, FlagStrategyProtocol, InterfacyParserCore
from interfacy_cli.exceptions import InvalidCommandError
from interfacy_cli.logger import logger as _logger
from interfacy_cli.themes import InterfacyTheme
from interfacy_cli.util import (
    AbbrevationGeneratorProtocol,
    DefaultAbbrevationGenerator,
    NoAbbrevations,
)


class ClickHelpFormatter(click.HelpFormatter):
    def __init__(
        self, indent_increment: int = 2, width: int | None = None, max_width: int | None = None
    ) -> None:
        try:
            terminal_width = get_terminal_size()[0]
        except OSError:
            terminal_width = 80
        super().__init__(indent_increment, width, terminal_width)


click.Context.formatter_class = ClickHelpFormatter


class ClickFuncParamType(click.types.FuncParamType):
    def __init__(self, func: T.Callable[[T.Any], T.Any], name: str | None = None) -> None:
        self.name = name or "NO_NAME"
        self.func = func


# Overwrite the original class so it works with functools.partial
click.types.FuncParamType = ClickFuncParamType


class ClickOption(click.Option):
    def get_help_record(self, ctx):
        help_record = super().get_help_record(ctx)
        if help_record is not None:
            name, help_text = help_record
            if " " in name:
                name = name.split(" ")[:-1]
                name = " ".join(name)
            return (name, help_text)
        return None

    def handle_parse_result(self, ctx, opts, args):
        value, args = super().handle_parse_result(ctx, opts, args)
        if self.is_flag and self.flag_value is not None:
            if value is None:  # Flag not present
                value = not self.flag_value
            else:
                value = self.flag_value
        return value, args


class ClickArgument(click.Argument):
    def __init__(
        self,
        param_decls: T.Sequence[str],
        required: T.Optional[bool] = None,
        help: T.Optional[str] = None,
        **attrs: T.Any,
    ):
        self.help = help
        super().__init__(param_decls, required=required, **attrs)

    def get_help_record(self, ctx):
        help_record = super().get_help_record(ctx)
        if help_record is not None:
            name, help_text = help_record
            # Remove metavar from the name part
            name = name.split(" ")[:-1]
            name = " ".join(name)
            return (name, help_text)
        return None


class ClickGroup(click.Group):
    def __init__(self, init_callback, name=None, commands=None, *args, **kwargs):
        super().__init__(name, commands, *args, **kwargs)
        self.init_callback = init_callback
        self.logger = _logger.bind(title=self.__class__.__name__)

    def invoke(self, ctx):
        self.logger.debug(f"initializing with params: {ctx.params}")
        instance = self.init_callback(**ctx.params)
        self.logger.debug(f"generated instance: {instance}")
        ctx.obj = instance
        super().invoke(ctx)

    def get_help(self, ctx) -> str:
        original_help = super().get_help(ctx)
        description, opts = original_help.split("Options:")
        options = "\n\nOptions:" + opts
        extra_help = "Positionals:\n"

        for param in self.params:
            if isinstance(param, ClickArgument):
                positional_name = f"{param.name}".ljust(16)
                arg_help = f"  {positional_name} {param.help or ''}".rjust(16) + "\n"
                extra_help += arg_help
        return description + extra_help + options


class ClickCommand(click.Command):
    def get_help(self, ctx) -> str:
        original_help = super().get_help(ctx)
        description, opts = original_help.split("Options:")
        options = "\n\nOptions:" + opts
        extra_help = "Positionals:\n"

        for param in self.params:
            if isinstance(param, ClickArgument):
                positional_name = f"{param.name}".ljust(16)
                arg_help = f"  {positional_name} {param.help or ''}".rjust(16) + "\n"
                extra_help += arg_help
        return description + extra_help + options


class UNSET: ...


class ClickParser(InterfacyParserCore):
    RESERVED_FLAGS = ["help"]

    def __init__(
        self,
        description: str | None = None,
        epilog: str | None = None,
        theme: InterfacyTheme | None = None,
        type_parser: StrToTypeParser | None = None,
        *,
        pipe_target: dict[str, str] | str | None = None,
        allow_args_from_file: bool = True,
        print_result: bool = True,
        print_result_func: T.Callable = click.echo,
        flag_strategy: FlagStrategyProtocol = DefaultFlagStrategy(),
        abbrev_gen: AbbrevationGeneratorProtocol = DefaultAbbrevationGenerator(),
        tab_completion: bool = False,
    ) -> None:
        super().__init__(
            description,
            epilog,
            theme,
            type_parser,
            pipe_target=pipe_target,
            allow_args_from_file=allow_args_from_file,
            print_result=print_result,
            print_result_func=print_result_func,
            flag_strategy=flag_strategy,
            tab_completion=tab_completion,
            abbrev_gen=abbrev_gen,
        )
        self.main_parser = click.Group(name="main")
        self.args = UNSET
        self.kwargs = UNSET

    def _handle_piped_input(self, command: str, params: dict[str, T.Any]) -> dict[str, T.Any]:
        piped = read_piped()
        if piped:
            if isinstance(self.pipe_target, str):
                params[self.pipe_target] = piped
            elif isinstance(self.pipe_target, dict):
                target = self.pipe_target.get(command)
                if target:
                    params[target] = piped
        return params

    def _generate_instance_callback(self, cls: Class) -> T.Callable:
        """
        Generates a function that instantiates the class with the given args.
        """

        def init_callback(*args, **kwargs):
            logger = _logger.bind(title="init_callback")
            logger.debug("Calling init_callback", args=args, kwargs=kwargs)
            if cls.is_initialized:
                ret = cls.instance
                logger.debug(f"Class is initialized already, returning {ret}")
                return ret
            ret = cls.cls(*args, **kwargs)
            logger.debug(f"Returning {ret}")
            return ret

        return init_callback

    def _generate_callback(
        self,
        fn: T.Callable,
        result_fn: T.Callable | None = None,
    ) -> T.Callable:
        logger = _logger.bind(title="_generate_callback")
        logger.debug(f"Generating callback for {fn}")

        def callback(*args, **kwargs):
            logger.debug(f"Calling callback for {fn}", args=args, kwargs=kwargs)
            self.args = args
            self.kwargs = kwargs

            if result_fn:
                result = result_fn()
            else:
                result = fn(*args, **kwargs)

            self.print_result_func(result)
            logger.debug(f"Result: {result}")
            return result

        return callback

    def _get_param(self, param: Parameter, taken_flags: list[str]) -> ClickOption | ClickArgument:
        name = self.flag_strategy.translator.translate(param.name)
        extras = {}
        extras["help"] = self.theme.get_parameter_help(param)
        extras["metavar"] = name

        if param.is_typed:
            parse_fn = self.type_parser.get_parse_func(param.type)
            parse_fn = ClickFuncParamType(parse_fn, f"parse_{name}")
            extras["type"] = parse_fn

        if param.is_required and self.flag_strategy.flags_style == "required_positional":
            opt_class = ClickArgument
            flags = (name,)
            taken_flags.append(name)
        else:
            opt_class = ClickOption
            if param.type is bool:
                if param.default is True:
                    flag_name = f"--no-{name}"
                    flags = (flag_name,)
                    extras["is_flag"] = True
                    extras["flag_value"] = False
                    extras["default"] = True
                else:
                    flags = self.flag_strategy.get_arg_flags(
                        name, param, taken_flags, self.abbrev_gen
                    )
                    extras["is_flag"] = True
                    extras["flag_value"] = True
                    extras["default"] = False
            else:
                flags = self.flag_strategy.get_arg_flags(name, param, taken_flags, self.abbrev_gen)
                if not param.is_required:
                    extras["default"] = param.default

        option = opt_class(
            flags,
            **extras,
        )
        return option

    def _parser_from_func(  # type:ignore
        self,
        fn: Function,
        taken_flags: list[str] | None = None,
        instance_callback: T.Callable | None = None,
    ) -> ClickCommand:
        if taken_flags is None:
            taken_flags = [*self.RESERVED_FLAGS]

        description = self.theme.format_description(fn.description) if fn.has_docstring else None
        params = [
            self._get_param(
                param,
                taken_flags,
            )
            for param in fn.params
        ]
        callback = self._generate_callback(fn.func, instance_callback)
        command = ClickCommand(
            name=fn.name,
            callback=callback,
            params=params,  # type: ignore
            help=description,
        )
        return command

    def _parser_from_class(self, cls: Class):  # type:ignore
        description = self.theme.format_description(cls.description) if cls.has_docstring else None

        params = []
        if cls.init_method and not cls.is_initialized:
            params.extend(
                [
                    self._get_param(
                        param,
                        [*self.reserved_flags],
                    )
                    for param in cls.init_method.params
                ],
            )

        init_callback = self._generate_instance_callback(cls)
        group = ClickGroup(
            name=cls.name,
            help=description,
            params=params,
            init_callback=init_callback,
        )

        def create_command_callback(method_func):
            @pass_context
            def command_callback(ctx, *args, **kwargs):
                instance = ctx.obj
                result = method_func(instance, *self.args, **self.kwargs)
                return result

            return command_callback

        for method in cls.methods:
            if method.name in self.method_skips or self._should_skip_method(method):
                continue
            command = self._parser_from_func(
                method,
                taken_flags=[*self.reserved_flags],
                instance_callback=create_command_callback(method.func),
            )
            group.add_command(command)
        return group

    def _parser_from_multiple(
        self,
        commands: list[Function | Class],
    ) -> click.Group:
        for cmd in commands:
            command_name = self.flag_strategy.translator.translate(cmd.name)
            parser = self._parser_from_object(cmd)
            self.main_parser.add_command(parser, name=command_name)
        return self.main_parser

    def add_command(self, command: T.Callable, name: str | None = None):
        self.main_parser.add_command(
            self._parser_from_object(inspect(command, inherited=False, private=False)),
            name=name,
        )

    def run(
        self,
        args: list[str] | None = None,
    ):
        args = args or self.get_args()
        self.main_parser.main(args=args)


__all__ = ["ClickParser"]

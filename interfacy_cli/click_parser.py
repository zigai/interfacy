import typing as T
from gettext import gettext as _
from os import get_terminal_size

import click
from click.exceptions import MissingParameter, UsageError, _join_param_hints
from objinspect import Class, Function, Method, Parameter, inspect
from strto import StrToTypeParser

from interfacy_cli.core import DefaultFlagStrategy, FlagStrategyProtocol, InterfacyParserCore
from interfacy_cli.exceptions import InvalidCommandError
from interfacy_cli.themes import InterfacyTheme
from interfacy_cli.util import AbbrevationGeneratorProtocol, DefaultAbbrevationGenerator

CLICK_RESERVED_FLAGS = ["help"]


class ClickOption(click.Option): ...


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


def missing_parameter_format_message(self) -> str:
    """
    if self.param_hint is not None:
        param_hint = self.param_hint
    elif self.param is not None:
        param_hint = self.param.get_error_hint(self.ctx)  # type: ignore
    else:
        param_hint = None
    param_hint = _join_param_hints(param_hint)
    param_hint = f" {param_hint}" if param_hint else ""
    if param_type is None and self.param is not None:
        param_type = self.param.param_type_name"""
    param_hint = f"{self.param.name.lower()}" if self.param is not None else ""
    param_type = self.param_type
    # Translate param_type for known types.
    if param_type == "argument":
        missing = _("Missing argument")
    elif param_type == "option":
        missing = _("Missing option")
    elif param_type == "parameter":
        missing = _("Missing parameter")
    else:
        missing = _(f"Missing {param_type}")
    msg = self.message
    if self.param is not None:
        msg_extra = self.param.type.get_missing_message(self.param)
        if msg_extra:
            msg = f"{msg}. {msg_extra}" if msg else msg_extra
    msg = f" {msg}" if msg else ""
    return f"{missing} '{param_hint}'.{msg}"


MissingParameter.format_message = missing_parameter_format_message


class ClickGroup(click.Group):
    def __init__(self, init_callback, name=None, commands=None, *args, **kwargs):
        super().__init__(name, commands, *args, **kwargs)
        self.init_callback = init_callback

    def invoke(self, ctx):
        instance = self.init_callback(**ctx.params)
        ctx.obj = instance
        super().invoke(ctx)


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


class ClickParser(InterfacyParserCore):
    RESERVED_FLAGS = ["help"]

    def __init__(
        self,
        description: str | None = None,
        epilog: str | None = None,
        theme: InterfacyTheme | None = None,
        type_parser: StrToTypeParser | None = None,
        *,
        pipe_target: str | None = None,
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

    def _generate_instance_callback(self, cls: Class) -> T.Callable:
        """
        Generates a function that instantiates the class with the given args.
        """

        def callback(*args, **kwargs):
            if cls.is_initialized:
                return cls.instance
            return cls.cls(*args, **kwargs)

        return callback

    def _generate_callback(
        self,
        fn: T.Callable,
        instance_callback: T.Callable | None = None,
    ) -> T.Callable:
        def callback(*args, **kwargs):
            if instance_callback:
                result = fn(instance_callback(), *args, **kwargs)
            else:
                result = fn(*args, **kwargs)
            self.print_result_func(result)
            return result

        return callback

    def _get_param(self, param: Parameter, taken_flags: list[str]) -> ClickOption | ClickArgument:
        """
        Generates a ClickOption or ClickArgument from a Parameter.

        Args:
            param (Parameter): The parameter to be converted.
            taken_flags (list[str]): A list of flags that are already in use.

        Returns:
            ClickOption | ClickArgument: The generated option or argument. Optional parameters are converted to options, required parameters are converted to arguments.

        """
        name = self.flag_strategy.translator.translate(param.name)

        extras = {}
        extras["help"] = self.theme.get_parameter_help(param)
        if self.theme.clear_metavar:
            extras["metavar"] = ""

        if param.is_typed:
            parse_fn = self.type_parser.get_parse_func(param.type)
            parse_fn = ClickFuncParamType(parse_fn, f"parse_{name}")
            extras["type"] = parse_fn

        if param.is_required:
            opt_class = ClickArgument
            flags = (name,)
            taken_flags.append(name)
        else:
            opt_class = ClickOption
            flags = self.flag_strategy.get_arg_flags(name, param, taken_flags, self.abbrev_gen)
            extras["default"] = param.default
            extras["is_flag"] = param.type is bool

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
        params = [self._get_param(param, taken_flags) for param in fn.params]
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
                    self._get_param(param, [*self.reserved_flags])
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

        if cls.receieved_instance:  # Don't need to provide instance to method call.
            init_callback = None

        for method in cls.methods:
            if method.name in self.method_skips:
                continue
            command = self._parser_from_func(
                method,
                taken_flags=[*self.reserved_flags],
                instance_callback=init_callback,
            )
            group.add_command(command)
        return group

    def _parser_from_multiple(
        self,
        commands: list[Function | Class],
    ) -> click.Group:
        main_parser = click.Group(name="main")
        for cmd in commands:
            command_name = self.flag_strategy.translator.translate(cmd.name)
            parser = self._parser_from_object(cmd)
            main_parser.add_command(parser, name=command_name)
        return main_parser

    def add_command(self, command: T.Callable, name: str | None = None):
        self.main_parser.add_command(
            self._parser_from_object(inspect(command, inherited=False)),
            name=name,
        )

    """
    def run(
        self,
        *commands: T.Callable,
        args: list[str] | None = None,
    ):
        args = args or self.get_args()
        commands_dict = self._collect_commands(*commands)
        if len(commands_dict) == 0:
            raise InvalidCommandError("No commands were provided.")

        if len(commands_dict) > 1:
            parser = self._parser_from_multiple([*commands_dict.values()])
        else:
            command = list(commands_dict.values()).pop()
            if isinstance(command, (Function, Method)):
                parser = self._parser_from_func(command, taken_flags=[*self.RESERVED_FLAGS])
            elif isinstance(command, Class):
                parser = self._parser_from_class(command)
            else:
                raise InvalidCommandError(f"Not a valid command: {command}")
        parser.main(args=args)
    """

    def run(
        self,
        args: list[str] | None = None,
    ):

        args = args or self.get_args()

        self.main_parser.main(args=args)


__all__ = ["ClickParser"]

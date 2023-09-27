import typing as T
from os import get_terminal_size

import click
import strto
from objinspect import Class, Function, Method, Parameter

from interfacy_cli.auto_parser_core import AutoParserCore
from interfacy_cli.constants import ARGPARSE_RESERVED_FLAGS, CLICK_RESERVED_FLAGS
from interfacy_cli.exceptions import InvalidCommandError
from interfacy_cli.themes import InterfacyTheme


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
        self.name = name or "XD"
        self.func = func


# Overwrite the original class so it works with functools.partial
click.types.FuncParamType = ClickFuncParamType


class ClickOption(click.Option):
    ...


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


class AutoClickParser(AutoParserCore):
    def __init__(
        self,
        description: str | None = None,
        epilog: str | None = None,
        theme: InterfacyTheme | None = None,
        value_parser: strto.Parser | None = None,
        *,
        flag_strategy: T.Literal["keyword_only", "required_positional"] = "required_positional",
        flag_translation_mode: T.Literal["none", "kebab", "snake"] = "kebab",
        from_file_prefix: str = "@F",
        print_result: bool = True,
        add_abbrevs: bool = True,
        read_stdin: bool = False,
        tab_completion: bool = False,
        allow_args_from_file: bool = True,
    ) -> None:
        super().__init__(
            description,
            epilog,
            theme,
            value_parser,
            flag_strategy=flag_strategy,
            flag_translation_mode=flag_translation_mode,
            from_file_prefix=from_file_prefix,
            add_abbrevs=add_abbrevs,
            read_stdin=read_stdin,
            print_result=print_result,
            allow_args_from_file=allow_args_from_file,
            tab_completion=tab_completion,
        )

    def display_result(self, value: T.Any) -> None:
        click.echo(value)

    def generate_instance_callback(self, cls: Class) -> T.Callable:
        """
        Generates a function that instantiates the class with the given args.
        """

        def callback(*args, **kwargs):
            if cls.is_initialized:
                return cls.instance
            return cls.cls(*args, **kwargs)

        return callback

    def generate_callback(
        self,
        fn: T.Callable,
        instance_callback: T.Callable | None = None,
    ) -> T.Callable:
        def callback(*args, **kwargs):
            if instance_callback:
                result = fn(instance_callback(), *args, **kwargs)
            else:
                result = fn(*args, **kwargs)
            self.display_result(result)
            return result

        return callback

    def get_param(self, param: Parameter, taken_flags: list[str]) -> ClickOption | ClickArgument:
        """
        Generates a ClickOption or ClickArgument from a Parameter.

        Args:
            param (Parameter): The parameter to be converted.
            taken_flags (list[str]): A list of flags that are already in use.

        Returns:
            ClickOption | ClickArgument: The generated option or argument. Optional parameters are converted to options, required parameters are converted to arguments.

        """
        name = self.translate_name(param.name)

        extras = {}
        extras["help"] = self.theme.get_parameter_help(param)
        if self.theme.clear_metavar:
            extras["metavar"] = ""

        if param.is_typed:
            parse_fn = self.value_parser.get_parse_fn(param.type)
            parse_fn = ClickFuncParamType(parse_fn, f"parse_{name}")
            extras["type"] = parse_fn

        if param.is_required:
            opt_class = ClickArgument
            flags = (name,)
            taken_flags.append(name)
        else:
            opt_class = ClickOption
            flags = self._get_arg_flags(name, param, taken_flags)
            extras["default"] = param.default
            extras["is_flag"] = param.type is bool

        option = opt_class(
            flags,
            **extras,
        )
        return option

    def parser_from_func(
        self,
        fn: Function,
        taken_flags: list[str] | None = None,
        instance_callback: T.Callable | None = None,
    ) -> ClickCommand:
        if taken_flags is None:
            taken_flags = [*CLICK_RESERVED_FLAGS]

        if fn.has_docstring:
            description = self.theme.format_description(fn.description)
        else:
            description = None

        params = [self.get_param(param, taken_flags) for param in fn.params]
        callback = self.generate_callback(fn.func, instance_callback)
        command = ClickCommand(
            name=fn.name,
            callback=callback,
            params=params,  # type: ignore
            help=description,
        )
        return command

    def parser_from_class(self, cls: Class):
        taken_flags = [*CLICK_RESERVED_FLAGS]
        if cls.has_docstring:
            description = self.theme.format_description(cls.description)
        else:
            description = None

        if cls.init_method and not cls.is_initialized:
            params = [self.get_param(param, taken_flags) for param in cls.init_method.params]
        else:
            params = []

        init_callback = self.generate_instance_callback(cls)
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
            command = self.parser_from_func(method, taken_flags, init_callback)
            group.add_command(command)

        return group

    def parser_from_multiple(
        self,
        commands: list[Function | Class],
    ) -> click.Group:
        main_parser = click.Group(name="main")
        for cmd in commands:
            command_name = self.translate_name(cmd.name)
            if isinstance(cmd, Function):
                parser = self.parser_from_func(fn=cmd, taken_flags=[*CLICK_RESERVED_FLAGS])
            elif isinstance(cmd, Class):
                parser = self.parser_from_class(cmd)
            elif isinstance(cmd, Method):
                parser = self.parser_from_func(cmd, taken_flags=[*CLICK_RESERVED_FLAGS])
            else:
                raise InvalidCommandError(f"Not a valid command: {cmd}")
            main_parser.add_command(parser, name=command_name)
        return main_parser

    def run(
        self,
        *commands: T.Callable,
        args: list[str] | None = None,
    ):
        args = args or self.get_args()
        commands_dict = self.collect_commands(*commands)
        if len(commands_dict) == 0:
            raise InvalidCommandError("No commands were provided.")

        if len(commands_dict) > 1:
            parser = self.parser_from_multiple([*commands_dict.values()])
        else:
            command = list(commands_dict.values()).pop()
            if isinstance(command, (Function, Method)):
                parser = self.parser_from_func(command, taken_flags=[*CLICK_RESERVED_FLAGS])
            elif isinstance(command, Class):
                parser = self.parser_from_class(command)
            else:
                raise InvalidCommandError(f"Not a valid command: {command}")
        parser.main(args=args)


__all__ = ["AutoClickParser"]

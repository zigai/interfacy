import typing as T
from gettext import gettext as _
from os import get_terminal_size

import click
from click import pass_context
from objinspect import Class, Function, Method, Parameter, inspect
from stdl.fs import read_piped
from strto import StrToTypeParser

from interfacy_cli.core import (
    DefaultFlagStrategy,
    FlagStrategyProtocol,
    InterfacyParserCore,
    inverted_bool_flag_name,
    show_result,
)
from interfacy_cli.exceptions import InvalidCommandError
from interfacy_cli.themes import InterfacyTheme
from interfacy_cli.util import (
    AbbrevationGeneratorProtocol,
    DefaultAbbrevationGenerator,
    NoAbbrevations,
    TranslationMapper,
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

    def invoke(self, ctx):
        instance = self.init_callback(**ctx.params)
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
        pipe_target: dict[str, str] | None = None,
        allow_args_from_file: bool = True,
        print_result: bool = False,
        print_result_func: T.Callable = show_result,
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
        self.bool_flag_translator = TranslationMapper(inverted_bool_flag_name)

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

    def _handle_bool_args(self, kwargs: dict):
        updated_kwargs = {}
        for k, v in kwargs.items():
            key = k.replace("_", "-")
            if self.bool_flag_translator.contains_translation(key):
                origin = self.bool_flag_translator.reverse(key)
                updated_kwargs[origin] = not v
            else:
                updated_kwargs[k] = v
        return updated_kwargs

    def revese_arg_translations(self, args: dict) -> dict[str, T.Any]:
        reversed = {}
        for k, v in args.items():
            reversed_k = self.flag_strategy.arg_translator.reverse(k)
            if reversed_k is not None:
                reversed[reversed_k] = v
            else:
                reversed[k] = v
        return reversed

    def _generate_instance_callback(self, cls: Class) -> T.Callable:
        """
        Generates a function that instantiates the class with the given args.
        """

        def init_callback(*args, **kwargs):
            if cls.is_initialized:
                ret = cls.instance
                return ret
            ret = cls.cls(*args, **kwargs)
            return ret

        return init_callback

    def _generate_callback(
        self,
        fn: Function,
        result_fn: T.Callable | None = None,
    ) -> T.Callable:

        def callback(*args, **kwargs):
            func = fn.func
            self.args = args
            self.kwargs = kwargs

            if result_fn:
                result = result_fn()
            else:
                updated_kwargs = self._handle_bool_args(kwargs)
                kwargs = self.revese_arg_translations(updated_kwargs)
                result = func(*args, **kwargs)
            if self.print_result:
                self.print_result_func(result)

            return result

        return callback

    def _is_pipe_target(self, name: str):
        if isinstance(self.pipe_target, str):
            return name == self.pipe_target
        if isinstance(self.pipe_target, dict):
            return name in self.pipe_target

    def _get_param(
        self, param: Parameter, taken_flags: list[str], command_name: str
    ) -> ClickOption | ClickArgument:
        name = self.flag_strategy.arg_translator.translate(param.name)
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
                    flag_name = self.bool_flag_translator.translate(name)
                    flag_name = f"--{flag_name}"
                    flags = (flag_name,)
                    extras["is_flag"] = True
                    extras["flag_value"] = True
                    extras["default"] = False
                else:
                    flags = self.flag_strategy.get_arg_flags(
                        name, param, taken_flags, self.abbrev_gen
                    )
                    extras["is_flag"] = True
                    extras["flag_value"] = False
                    extras["default"] = True
            else:
                flags = self.flag_strategy.get_arg_flags(name, param, taken_flags, self.abbrev_gen)
                if not param.is_required:
                    extras["default"] = param.default

        pipe_target_for_command = (
            self.pipe_target.get(command_name, None) if self.pipe_target is not None else None
        )

        if pipe_target_for_command == param.name:
            extras["default"] = self.piped

        option = opt_class(
            flags,
            **extras,
        )
        return option

    def _parser_from_func(  # type:ignore
        self,
        fn: Function | Method,
        taken_flags: list[str] | None = None,
        instance_callback: T.Callable | None = None,
    ) -> ClickCommand:
        if taken_flags is None:
            taken_flags = [*self.RESERVED_FLAGS]
        command_name = self.flag_strategy.command_translator.translate(fn.name)
        description = self.theme.format_description(fn.description) if fn.has_docstring else None
        params = [self._get_param(param, taken_flags, command_name=fn.name) for param in fn.params]
        callback = self._generate_callback(fn, instance_callback)
        command = ClickCommand(
            name=command_name,
            callback=callback,
            params=params,  # type: ignore
            help=description,
        )
        return command

    def _parser_from_class(self, cls: Class):  # type:ignore
        description = self.theme.format_description(cls.description) if cls.has_docstring else None
        command_name = self.flag_strategy.command_translator.translate(cls.name)
        params = []
        if cls.init_method and not cls.is_initialized:
            params.extend(
                [
                    self._get_param(param, [*self.RESERVED_FLAGS], command_name="__init__")
                    for param in cls.init_method.params
                ],
            )

        init_callback = self._generate_instance_callback(cls)
        group = ClickGroup(
            name=command_name,
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
                taken_flags=[*self.RESERVED_FLAGS],
                instance_callback=create_command_callback(method.func),
            )
            group.add_command(command)
        return group

    def _parser_from_multiple(
        self,
        commands: list[Function | Class],
    ) -> click.Group:
        for cmd in commands:
            command_name = self.flag_strategy.arg_translator.translate(cmd.name)
            parser = self._parser_from_object(cmd)
            self.main_parser.add_command(parser, name=command_name)
        return self.main_parser

    def add_command(self, command: T.Callable, name: str | None = None):
        self.main_parser.add_command(
            self._parser_from_object(inspect(command, inherited=False, private=False)),
            name=name,
        )

    def run(self, *commands: T.Callable, args: list[str] | None = None):
        if commands:
            if len(commands) == 1:
                command = commands[0]
                parser = self._parser_from_object(inspect(command, inherited=False, private=False))
                self.main_parser = parser
            else:
                for i in commands:
                    self.add_command(i)
        args = args or self.get_args()
        self.main_parser.main(args=args)


__all__ = ["ClickParser"]

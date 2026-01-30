from collections.abc import Callable, Sequence
from os import get_terminal_size
from typing import Any, ClassVar

import click
from click import pass_context
from objinspect import Class, Function, Method, Parameter, inspect
from stdl.fs import read_piped
from strto import StrToTypeParser

from interfacy.appearance.layout import HelpLayout, InterfacyColors
from interfacy.core import InterfacyParser
from interfacy.naming import AbbreviationGenerator, FlagStrategy, NameMapping
from interfacy.pipe import PipeTargets
from interfacy.util import inverted_bool_flag_name, resolve_type_alias


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
    def __init__(self, func: Callable[[Any], Any], name: str | None = None) -> None:
        super().__init__(func)
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
            return name, help_text
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
        param_decls: Sequence[str],
        required: bool | None = None,
        help: str | None = None,
        **attrs: Any,
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
            return name, help_text
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


class ClickParser(InterfacyParser):
    RESERVED_FLAGS: ClassVar[list[str]] = ["help"]

    def __init__(
        self,
        description: str | None = None,
        epilog: str | None = None,
        type_parser: StrToTypeParser | None = None,
        help_layout: HelpLayout | None = None,
        *,
        help_colors: InterfacyColors | None = None,
        run: bool = False,
        print_result: bool = False,
        tab_completion: bool = False,
        full_error_traceback: bool = False,
        allow_args_from_file: bool = True,
        sys_exit_enabled: bool = True,
        flag_strategy: FlagStrategy | None = None,
        abbreviation_gen: AbbreviationGenerator | None = None,
        pipe_targets: PipeTargets | dict[str, str] | str | None = None,
        print_result_func: Callable = print,
        include_inherited_methods: bool = False,
        include_classmethods: bool = False,
    ) -> None:
        super().__init__(
            description,
            epilog,
            help_layout,
            type_parser,
            help_colors=help_colors,
            pipe_targets=None,
            allow_args_from_file=allow_args_from_file,
            print_result=print_result,
            print_result_func=print_result_func,
            flag_strategy=flag_strategy,
            tab_completion=tab_completion,
            abbreviation_gen=abbreviation_gen,
            include_inherited_methods=include_inherited_methods,
            include_classmethods=include_classmethods,
        )
        self.main_parser = click.Group(name="main")
        self.args = UNSET
        self.kwargs = UNSET
        self.bool_flag_translator = NameMapping(inverted_bool_flag_name)
        if isinstance(pipe_targets, PipeTargets):
            target_names = list(pipe_targets.targets)
            if len(target_names) == 1:
                self.pipe_target = target_names[0]
            else:
                self.pipe_target = None
        else:
            self.pipe_target = pipe_targets

    def _handle_piped_input(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
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

    def reverse_arg_translations(self, args: dict) -> dict[str, Any]:
        reversed_args: dict[str, Any] = {}
        for key, value in args.items():
            canonical_key = self.flag_strategy.argument_translator.reverse(key)
            if canonical_key is not None:
                reversed_args[canonical_key] = value
            else:
                reversed_args[key] = value
        return reversed_args

    def _generate_instance_callback(self, cls: Class) -> Callable:
        """Generates a function that instantiates the class with the given args."""

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
        result_fn: Callable | None = None,
    ) -> Callable:
        def callback(*args, **kwargs):
            func = fn.func
            self.args = args
            self.kwargs = kwargs

            if result_fn:
                result = result_fn()
            else:
                updated_kwargs = self._handle_bool_args(kwargs)
                kwargs = self.reverse_arg_translations(updated_kwargs)
                result = func(*args, **kwargs)
            if self.display_result:
                self.result_display_fn(result)

            return result

        return callback

    def _is_pipe_target(self, name: str):
        if isinstance(self.pipe_target, str):
            return name == self.pipe_target
        if isinstance(self.pipe_target, dict):
            return name in self.pipe_target
        return False

    def _get_param(
        self, param: Parameter, taken_flags: list[str], command_name: str
    ) -> ClickOption | ClickArgument:
        name = self.flag_strategy.argument_translator.translate(param.name)
        extras: dict = {
            "help": self.help_layout.get_help_for_parameter(param),
            "metavar": name,
        }

        if param.is_typed:
            annotation = resolve_type_alias(param.type)
            parse_fn = self.type_parser.get_parse_func(annotation)
            parse_fn = ClickFuncParamType(parse_fn, f"parse_{name}")
            extras["type"] = parse_fn

        if param.is_required and self.flag_strategy.style == "required_positional":
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
                        name, param, taken_flags, self.abbreviation_gen
                    )
                    extras["is_flag"] = True
                    extras["flag_value"] = False
                    extras["default"] = True
            else:
                flags = self.flag_strategy.get_arg_flags(
                    name, param, taken_flags, self.abbreviation_gen
                )
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

    def parser_from_function(  # type:ignore
        self,
        fn: Function | Method,
        taken_flags: list[str] | None = None,
        instance_callback: Callable | None = None,
    ) -> ClickCommand:
        if taken_flags is None:
            taken_flags = [*self.RESERVED_FLAGS]
        command_name = self.flag_strategy.command_translator.translate(fn.name)
        description = (
            self.help_layout.format_description(fn.description) if fn.has_docstring else None
        )
        params = [self._get_param(param, taken_flags, command_name=fn.name) for param in fn.params]
        callback = self._generate_callback(fn, instance_callback)
        command = ClickCommand(
            name=command_name,
            callback=callback,
            params=params,  # type: ignore
            help=description,
        )
        return command

    def parser_from_class(self, cls: Class):  # type:ignore
        description = (
            self.help_layout.format_description(cls.description) if cls.has_docstring else None
        )
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
            command = self.parser_from_function(
                method,
                taken_flags=[*self.RESERVED_FLAGS],
                instance_callback=create_command_callback(method.func),
            )
            group.add_command(command)
        return group

    def parser_from_multiple_commands(
        self,
        commands: list[Function | Class],
    ) -> click.Group:
        for cmd in commands:
            command_name = self.flag_strategy.argument_translator.translate(cmd.name)
            parser = self.parser_from_command(cmd)
            self.main_parser.add_command(parser, name=command_name)
        return self.main_parser

    def add_command(self, command: Callable, name: str | None = None):
        self.main_parser.add_command(
            self.parser_from_command(inspect(command, inherited=False, private=False)),
            name=name,
        )

    def run(self, *commands: Callable, args: list[str] | None = None):
        if commands:
            if len(commands) == 1:
                command = commands[0]
                parser = self.parser_from_command(inspect(command, inherited=False, private=False))
                self.main_parser = parser
            else:
                for i in commands:
                    self.add_command(i)
        args = args or self.get_args()
        self.main_parser.main(args=args)


__all__ = ["ClickParser"]

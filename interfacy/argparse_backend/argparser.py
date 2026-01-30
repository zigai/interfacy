from __future__ import annotations

import argparse
import signal
import sys
import time
from collections.abc import Callable, Sequence
from typing import Any, ClassVar

from objinspect import Class, Function, Method, Parameter
from objinspect.typing import type_args
from strto import StrToTypeParser

from interfacy import console
from interfacy.appearance.layout import HelpLayout, InterfacyColors
from interfacy.argparse_backend.argument_parser import ArgumentParser, namespace_to_dict
from interfacy.argparse_backend.help_formatter import InterfacyHelpFormatter
from interfacy.argparse_backend.runner import ArgparseRunner
from interfacy.core import ExitCode, InterfacyParser
from interfacy.exceptions import (
    ConfigurationError,
    DuplicateCommandError,
    InterfacyError,
    InvalidCommandError,
    ReservedFlagError,
    UnsupportedParameterTypeError,
)
from interfacy.logger import get_logger
from interfacy.naming import AbbreviationGenerator, FlagStrategy
from interfacy.pipe import PipeTargets
from interfacy.schema.schema import (
    Argument,
    ArgumentKind,
    Command,
    ParserSchema,
    ValueShape,
)
from interfacy.util import (
    extract_optional_union_list,
    get_param_choices,
    is_list_or_list_alias,
    resolve_type_alias,
)

logger = get_logger(__name__)


class Argparser(InterfacyParser):
    RESERVED_FLAGS: ClassVar[list[str]] = ["help"]
    COMMAND_KEY = "command"

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
        pipe_targets: PipeTargets | dict[str, Any] | Sequence[Any] | str | None = None,
        print_result_func: Callable = print,
        include_inherited_methods: bool = False,
        include_classmethods: bool = False,
        on_interrupt: Callable[[KeyboardInterrupt], None] | None = None,
        silent_interrupt: bool = True,
        reraise_interrupt: bool = False,
        expand_model_params: bool = True,
        model_expansion_max_depth: int = 3,
        use_global_config: bool = False,
        formatter_class: type[argparse.HelpFormatter] = InterfacyHelpFormatter,
    ) -> None:
        if use_global_config:
            from interfacy.cli.config import apply_config_defaults, load_config

            overrides = apply_config_defaults(
                load_config(),
                {
                    "flag_strategy": flag_strategy,
                    "help_layout": help_layout,
                    "help_colors": help_colors,
                    "print_result": print_result,
                    "full_error_traceback": full_error_traceback,
                    "tab_completion": tab_completion,
                    "allow_args_from_file": allow_args_from_file,
                    "include_inherited_methods": include_inherited_methods,
                    "include_classmethods": include_classmethods,
                    "silent_interrupt": silent_interrupt,
                    "abbreviation_gen": abbreviation_gen,
                    "expand_model_params": expand_model_params,
                    "model_expansion_max_depth": model_expansion_max_depth,
                },
            )

            flag_strategy = overrides["flag_strategy"]
            help_layout = overrides["help_layout"]
            help_colors = overrides["help_colors"]
            print_result = overrides["print_result"]
            full_error_traceback = overrides["full_error_traceback"]
            tab_completion = overrides["tab_completion"]
            allow_args_from_file = overrides["allow_args_from_file"]
            include_inherited_methods = overrides["include_inherited_methods"]
            include_classmethods = overrides["include_classmethods"]
            silent_interrupt = overrides["silent_interrupt"]
            abbreviation_gen = overrides["abbreviation_gen"]
            expand_model_params = overrides["expand_model_params"]
            model_expansion_max_depth = overrides["model_expansion_max_depth"]

        super().__init__(
            description,
            epilog,
            help_layout,
            type_parser,
            help_colors=help_colors,
            run=run,
            allow_args_from_file=allow_args_from_file,
            flag_strategy=flag_strategy,
            abbreviation_gen=abbreviation_gen,
            pipe_targets=pipe_targets,
            tab_completion=tab_completion,
            print_result=print_result,
            print_result_func=print_result_func,
            full_error_traceback=full_error_traceback,
            sys_exit_enabled=sys_exit_enabled,
            include_inherited_methods=include_inherited_methods,
            include_classmethods=include_classmethods,
            on_interrupt=on_interrupt,
            silent_interrupt=silent_interrupt,
            reraise_interrupt=reraise_interrupt,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=model_expansion_max_depth,
        )
        self.formatter_class = formatter_class
        self._parser: ArgumentParser | None = None
        self._last_interrupt_time: float = 0.0
        self._last_schema: ParserSchema | None = None
        del self.type_parser.parsers[list]

    def _new_parser(self, name: str | None = None) -> ArgumentParser:
        return ArgumentParser(
            name, formatter_class=self.formatter_class, help_layout=self.help_layout
        )

    def _add_parameter_to_parser(
        self,
        param: Parameter,
        parser: ArgumentParser,
        taken_flags: list[str],
    ) -> argparse.Action:
        if param.name in taken_flags:
            raise ReservedFlagError(param.name)

        name = self.flag_strategy.argument_translator.translate(param.name)
        flags = self.flag_strategy.get_arg_flags(name, param, taken_flags, self.abbreviation_gen)
        extra_args = self._extra_add_arg_params(param, flags)
        logger.info(f"Flags: {flags}, Extra args: {extra_args}")
        return parser.add_argument(*flags, **extra_args)

    def parser_from_function(
        self,
        function: Function,
        parser: ArgumentParser | None = None,
        taken_flags: list[str] | None = None,
    ) -> ArgumentParser:
        """Create an ArgumentParser from a Function"""
        taken_flags = [] if taken_flags is None else taken_flags
        parser = parser or self._new_parser()

        if function.has_docstring:
            parser.description = self.help_layout.format_description(function.description)

        for param in function.params:
            self._add_parameter_to_parser(param=param, parser=parser, taken_flags=taken_flags)

        return parser

    def parser_from_method(
        self,
        method: Method,
        taken_flags: list[str],
        parser: ArgumentParser | None = None,
    ) -> ArgumentParser:
        """Create an ArgumentParser from a Method"""
        parser = parser or self._new_parser()

        is_initialized = hasattr(method.func, "__self__")
        if (init := Class(method.cls).init_method) and not is_initialized:
            for param in init.params:
                self._add_parameter_to_parser(param=param, parser=parser, taken_flags=taken_flags)

        for param in method.params:
            self._add_parameter_to_parser(param=param, parser=parser, taken_flags=taken_flags)

        if method.has_docstring:
            parser.description = self.help_layout.format_description(method.description)

        return parser

    def parser_from_class(
        self,
        cls: Class,
        parser: ArgumentParser | None = None,
        subparser: argparse._SubParsersAction[ArgumentParser] | None = None,
    ) -> ArgumentParser:
        """Create an ArgumentParser from a Class"""
        parser = parser or self._new_parser()

        if cls.has_docstring:
            parser.description = self.help_layout.format_description(cls.description)
        parser.epilog = self.help_layout.get_help_for_class(cls)  # type: ignore

        if cls.has_init and not cls.is_initialized:
            for param in cls.get_method("__init__").params:
                self._add_parameter_to_parser(
                    parser=parser,
                    param=param,
                    taken_flags=[*self.RESERVED_FLAGS, self.COMMAND_KEY],
                )

        if subparser is None:
            subparser = parser.add_subparsers(dest=self.COMMAND_KEY, required=True)

        for method in cls.methods:
            if method.name in self.method_skips:
                continue
            taken_flags = [*self.RESERVED_FLAGS]
            method_name = self.flag_strategy.command_translator.translate(method.name)
            sp = subparser.add_parser(method_name, description=method.description)
            self.parser_from_function(function=method, parser=sp, taken_flags=taken_flags)

        return parser

    def _extra_add_arg_params(self, param: Parameter, flags: tuple[str, ...]) -> dict[str, Any]:
        """
        This method creates a dictionary with additional argument parameters needed to
        customize argparse's `add_argument` method based on a given `Parameter` object.

        Args:
            param (Parameter): The parameter for which to construct additional parameters.
            flags (tuple[str, ...]): The flags to be used for the argument.

        Returns:
            dict[str, Any]: A dictionary containing additional parameter settings like "help",
            "required", "metavar", and "default".

        """
        extra: dict[str, Any] = {}
        if self.help_layout._use_template_layout():  # type: ignore[attr-defined]
            extra["help"] = self.help_layout.get_help_for_parameter(param, None)
        else:
            extra["help"] = self.help_layout.get_help_for_parameter(param, flags)

        annotation = resolve_type_alias(param.type) if param.is_typed else None
        is_bool_param = param.is_typed and annotation is bool
        if param.is_typed and not is_bool_param:
            optional_union_list = extract_optional_union_list(annotation)
            list_annotation: Any | None = None
            element_type: Any | None = None

            if optional_union_list:
                list_annotation, element_type = optional_union_list
            elif is_list_or_list_alias(annotation):
                list_annotation = annotation
                list_args = type_args(annotation)
                element_type = list_args[0] if list_args else None

            if list_annotation is not None:
                extra["nargs"] = "*"
                if element_type is not None:
                    extra["type"] = self.type_parser.get_parse_func(element_type)
            else:
                extra["type"] = self.type_parser.get_parse_func(annotation)

            if choices := get_param_choices(param, for_display=False):
                extra["choices"] = self._coerce_choices_for_parser(choices, extra.get("type"))

        if self.help_layout.clear_metavar and not is_bool_param:
            if not param.is_required:
                extra["metavar"] = "\b"

        if self.flag_strategy.style == "required_positional":
            is_positional = all([not i.startswith("-") for i in flags])
            logger.debug(f"Flags: {flags}, positional={is_positional}")
            if not is_positional:
                extra["required"] = param.is_required

        if is_bool_param:
            extra["action"] = argparse.BooleanOptionalAction
            if not param.is_required:
                extra["default"] = param.default
            else:
                extra["default"] = False
            return extra

        if not param.is_required:
            extra["default"] = param.default
        return extra

    def _argument_kwargs(self, arg: Argument) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"help": arg.help or ""}
        is_boolean_flag = arg.value_shape == ValueShape.FLAG

        if arg.metavar and not is_boolean_flag:
            kwargs["metavar"] = arg.metavar
        if arg.nargs and not is_boolean_flag:
            kwargs["nargs"] = arg.nargs

        if is_boolean_flag:
            kwargs["action"] = argparse.BooleanOptionalAction
            if arg.boolean_behavior is not None:
                kwargs["default"] = arg.boolean_behavior.default
        else:
            if arg.parser is not None:
                kwargs["type"] = arg.parser
            if arg.choices:
                kwargs["choices"] = self._coerce_choices_for_parser(arg.choices, arg.parser)
            if not arg.required:
                kwargs["default"] = arg.default

        if self.flag_strategy.style == "required_positional" and arg.kind == ArgumentKind.OPTION:
            kwargs["required"] = arg.required

        return kwargs

    def _add_argument_from_schema(self, parser: ArgumentParser, argument: Argument) -> None:
        kwargs = self._argument_kwargs(argument)
        logger.info(f"Adding argument flags={argument.flags}, kwargs={kwargs}")
        parser.add_argument(*argument.flags, **kwargs)

    @staticmethod
    def _coerce_choices_for_parser(
        choices: Sequence[Any] | None, parser: Callable[[str], Any] | None
    ) -> Sequence[Any] | None:
        if not choices or parser is None:
            return choices
        if not all(isinstance(choice, str) for choice in choices):
            return choices

        converted: list[Any] = []
        for choice in choices:
            try:
                converted.append(parser(choice))
            except Exception:
                return choices
        return converted

    def _apply_command_schema(
        self,
        parser: ArgumentParser,
        command: Command,
        *,
        depth: int = 0,
    ) -> None:
        if command.description:
            parser.description = command.description

        if not command.is_leaf and command.subcommands:
            for argument in command.initializer:
                self._add_argument_from_schema(parser, argument)

            if command.epilog:
                parser.epilog = command.epilog

            dest = f"{self.COMMAND_KEY}_{depth}" if depth > 0 else self.COMMAND_KEY
            subparsers = parser.add_subparsers(
                dest=dest,
                required=True,
                help=argparse.SUPPRESS if command.epilog else None,
            )
            for sub_cmd in command.subcommands.values():
                subparser = subparsers.add_parser(
                    sub_cmd.cli_name,
                    description=sub_cmd.description,
                    aliases=list(sub_cmd.aliases) if sub_cmd.aliases else [],
                )
                self._apply_command_schema(subparser, sub_cmd, depth=depth + 1)
            return

        if isinstance(command.obj, Class):
            for argument in command.initializer:
                self._add_argument_from_schema(parser, argument)

            if command.epilog:
                parser.epilog = command.epilog

            dest = f"{self.COMMAND_KEY}_{depth}" if depth > 0 else self.COMMAND_KEY
            subparsers = parser.add_subparsers(
                dest=dest,
                required=True,
                help=argparse.SUPPRESS if command.epilog else None,
            )
            if command.subcommands:
                for sub_cmd in command.subcommands.values():
                    subparser = subparsers.add_parser(
                        sub_cmd.cli_name,
                        description=sub_cmd.description,
                    )
                    self._apply_command_schema(subparser, sub_cmd, depth=depth + 1)
            return

        if isinstance(command.obj, Method) and command.initializer:
            for argument in command.initializer:
                self._add_argument_from_schema(parser, argument)

        for argument in command.parameters:
            self._add_argument_from_schema(parser, argument)

    def _build_from_schema(self, schema: ParserSchema) -> ArgumentParser:
        parser = self._new_parser()

        single_cmd = next(iter(schema.commands.values())) if len(schema.commands) == 1 else None
        single_group = single_cmd if single_cmd and not single_cmd.is_leaf else None

        if schema.is_multi_command or single_group:
            subparsers = parser.add_subparsers(
                dest=self.COMMAND_KEY,
                required=True,
                help=argparse.SUPPRESS if schema.commands_help else None,
            )
            for _, cmd in schema.commands.items():
                subparser = subparsers.add_parser(
                    cmd.cli_name,
                    description=cmd.description,
                    aliases=list(cmd.aliases),
                )
                self._apply_command_schema(subparser, cmd)

            if schema.commands_help:
                parser.epilog = schema.commands_help
        else:
            cmd = next(iter(schema.commands.values()))
            self._apply_command_schema(parser, cmd)

            if cmd.epilog and not parser.epilog:
                parser.epilog = cmd.epilog

        if schema.description:
            parser.description = schema.description

        if schema.epilog:
            existing = parser.epilog or ""
            parser.epilog = f"{existing}\n\n{schema.epilog}".strip()

        return parser

    def install_tab_completion(self, parser: ArgumentParser) -> None:
        """
        Install tab completion for the given parser.
        Requires the argcomplete package to be installed.

        'pip install argcomplete'
        """
        try:
            import argcomplete

        except ImportError:
            console.warn(
                "argcomplete not installed. Tab completion not available."
                " Install with 'pip install argcomplete'"
            )
            return

        argcomplete.autocomplete(parser)

    def build_parser(self) -> ArgumentParser:
        if not self.commands:
            raise ConfigurationError("No commands were provided")

        schema = self.build_parser_schema()
        self._last_schema = schema
        parser = self._build_from_schema(schema)

        if self.enable_tab_completion:
            self.install_tab_completion(parser)
        return parser

    def parse_args(self, args: list[str] | None = None) -> dict[str, Any]:
        args = args if args is not None else self.get_args()
        parser = self.build_parser()
        self._parser = parser
        parsed = parser.parse_args(args)
        namespace = namespace_to_dict(parsed)

        if self.COMMAND_KEY in namespace:
            cli_name = namespace[self.COMMAND_KEY]
            canonical = self.name_registry.canonical_for(cli_name) or cli_name
            namespace[self.COMMAND_KEY] = canonical

            if canonical in namespace:
                pass
            elif cli_name in namespace:
                namespace[canonical] = namespace.pop(cli_name)
            else:
                namespace[canonical] = {}

        namespace = self._convert_tuple_args(namespace)
        return namespace

    def _convert_tuple_args(self, namespace: dict[str, Any]) -> dict[str, Any]:
        """Convert arguments with ValueShape.TUPLE from list to tuple, applying per-element parsers."""
        schema = getattr(self, "_last_schema", None) or self.build_parser_schema()

        def convert_tuple(arg: Argument, val: list[Any]) -> tuple[Any, ...]:
            if arg.tuple_element_parsers:
                return tuple(
                    parser(v) for parser, v in zip(arg.tuple_element_parsers, val, strict=False)
                )
            return tuple(val)

        for command in schema.commands.values():
            for arg in command.initializer:
                if arg.value_shape == ValueShape.TUPLE and arg.name in namespace:
                    val = namespace[arg.name]
                    if isinstance(val, list):
                        namespace[arg.name] = convert_tuple(arg, val)

            for arg in command.parameters:
                if arg.value_shape == ValueShape.TUPLE and arg.name in namespace:
                    val = namespace[arg.name]
                    if isinstance(val, list):
                        namespace[arg.name] = convert_tuple(arg, val)

            if command.subcommands:
                for subcmd in command.subcommands.values():
                    cmd_key = self.COMMAND_KEY
                    if cmd_key in namespace and subcmd.cli_name in namespace:
                        sub_ns = namespace[subcmd.cli_name]
                        if isinstance(sub_ns, dict):
                            for arg in subcmd.parameters:
                                if arg.value_shape == ValueShape.TUPLE and arg.name in sub_ns:
                                    val = sub_ns[arg.name]
                                    if isinstance(val, list):
                                        sub_ns[arg.name] = convert_tuple(arg, val)

        return namespace

    def _handle_interrupt(self, exc: KeyboardInterrupt) -> KeyboardInterrupt:
        """Handle KeyboardInterrupt with callback, logging, and optional re-raise."""
        if self.on_interrupt is not None:
            self.on_interrupt(exc)
        self.log_interrupt()
        self.exit(ExitCode.INTERRUPTED)
        if self.reraise_interrupt:
            raise exc
        return exc

    def run(self, *commands: Callable | type | object, args: list[str] | None = None) -> Any:
        original_handler = signal.getsignal(signal.SIGINT)

        def sigint_handler(signum: int, frame: Any) -> None:
            now = time.time()
            if now - self._last_interrupt_time < 1.0:  # Double Ctrl+C: force immediate exit
                sys.exit(ExitCode.INTERRUPTED)
            self._last_interrupt_time = now
            raise KeyboardInterrupt()

        signal.signal(signal.SIGINT, sigint_handler)

        try:
            self.reset_piped_input()
            for cmd in commands:
                self.add_command(cmd, name=None, description=None)

            args = args if args is not None else self.get_args()
            logger.info(f"Got args: {args}")
            namespace = self.parse_args(args)
        except (
            DuplicateCommandError,
            UnsupportedParameterTypeError,
            ReservedFlagError,
            InvalidCommandError,
            ConfigurationError,
        ) as e:
            self.log_exception(e)
            self.exit(ExitCode.ERR_PARSING)
            return e
        except KeyboardInterrupt as e:
            return self._handle_interrupt(e)
        finally:
            signal.signal(signal.SIGINT, original_handler)

        signal.signal(signal.SIGINT, sigint_handler)
        try:
            runner = ArgparseRunner(
                namespace=namespace,
                args=args,
                parser=self._parser,
                builder=self,
            )
            result = runner.run()
        except InterfacyError as e:
            self.log_exception(e)
            self.exit(ExitCode.ERR_RUNTIME_INTERNAL)
            return e
        except KeyboardInterrupt as e:
            return self._handle_interrupt(e)
        except Exception as e:
            self.log_exception(e)
            self.exit(ExitCode.ERR_RUNTIME)
            return e
        finally:
            signal.signal(signal.SIGINT, original_handler)

        if self.display_result:
            self.result_display_fn(result)

        self.exit(ExitCode.SUCCESS)
        return result

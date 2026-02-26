from __future__ import annotations

import argparse
import re
import signal
import sys
import time
from collections.abc import Callable, Sequence
from types import FrameType
from typing import Any, ClassVar, Literal

from objinspect import Class, Function, Method, Parameter
from objinspect.typing import type_args
from strto import StrToTypeParser

from interfacy import console
from interfacy.appearance.layout import HelpLayout, InterfacyColors
from interfacy.argparse_backend.argument_parser import (
    ArgumentParser,
    NestedSubParsersAction,
    namespace_to_dict,
)
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
    """
    Argparse-backed Interfacy parser implementation.

    Args:
        description (str | None): CLI description shown in help output.
        epilog (str | None): Epilog text shown after help output.
        type_parser (StrToTypeParser | None): Parser registry for typed arguments.
        help_layout (HelpLayout | None): Help layout implementation.
        help_colors (InterfacyColors | None): Override help color theme.
        run (bool): Whether to auto-run after command registration.
        print_result (bool): Whether to print returned results.
        tab_completion (bool): Whether to enable tab completion.
        full_error_traceback (bool): Whether to print full tracebacks.
        allow_args_from_file (bool): Allow @file argument expansion.
        sys_exit_enabled (bool): Whether to call sys.exit on completion.
        flag_strategy (FlagStrategy | None): Flag naming and style strategy.
        abbreviation_gen (AbbreviationGenerator | None): Abbreviation generator.
        abbreviation_max_generated_len (int): Max generated short-flag length.
        abbreviation_scope (Literal["top_level_options", "all_options"]): Scope for generation.
        help_option_sort (Literal["declaration", "alphabetical"]): Help option row ordering.
        pipe_targets (PipeTargets | dict[str, Any] | Sequence[Any] | str | None): Pipe config.
        print_result_func (Callable): Function used to print results.
        include_inherited_methods (bool): Include inherited methods for class commands.
        include_classmethods (bool): Include classmethods as commands.
        on_interrupt (Callable[[KeyboardInterrupt], None] | None): Interrupt callback.
        silent_interrupt (bool): Suppress interrupt message output.
        reraise_interrupt (bool): Re-raise KeyboardInterrupt after handling.
        expand_model_params (bool): Expand model parameters into nested flags.
        model_expansion_max_depth (int): Max depth for model expansion.
        formatter_class (type[argparse.HelpFormatter]): Help formatter class.
    """

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
        abbreviation_max_generated_len: int = 1,
        abbreviation_scope: Literal["top_level_options", "all_options"] = "top_level_options",
        help_option_sort: Literal["declaration", "alphabetical"] = "declaration",
        pipe_targets: PipeTargets | dict[str, Any] | Sequence[Any] | str | None = None,
        print_result_func: Callable[[Any], Any] = print,
        include_inherited_methods: bool = False,
        include_classmethods: bool = False,
        on_interrupt: Callable[[KeyboardInterrupt], None] | None = None,
        silent_interrupt: bool = True,
        reraise_interrupt: bool = False,
        expand_model_params: bool = True,
        model_expansion_max_depth: int = 3,
        formatter_class: type[argparse.HelpFormatter] = InterfacyHelpFormatter,
    ) -> None:
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
            abbreviation_max_generated_len=abbreviation_max_generated_len,
            abbreviation_scope=abbreviation_scope,
            help_option_sort=help_option_sort,
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
        add_flags = flags
        if extra_args.get("action") is argparse.BooleanOptionalAction:
            add_flags = self._normalize_boolean_optional_flags(flags)
        logger.info("Flags: %s, Extra args: %s", flags, extra_args)
        return parser.add_argument(*add_flags, **extra_args)

    def parser_from_function(
        self,
        function: Function,
        parser: ArgumentParser | None = None,
        taken_flags: list[str] | None = None,
    ) -> ArgumentParser:
        """Create an ArgumentParser from a Function."""
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
        """Create an ArgumentParser from a Method."""
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
        subparser: NestedSubParsersAction | None = None,
    ) -> ArgumentParser:
        """Create an ArgumentParser from a Class."""
        parser = parser or self._new_parser()

        if cls.has_docstring:
            parser.description = self.help_layout.format_description(cls.description)
        parser.epilog = self.help_layout.get_help_for_class(cls)

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

        self._set_subparsers_metavar(subparser)

        return parser

    def parser_from_multiple_commands(self, *args: object, **_kwargs: object) -> ArgumentParser:
        """
        Create an ArgumentParser from multiple commands.

        Positional arguments are treated as commands to register before building the parser.
        """
        for command in args:
            self.add_command(command)
        return self.build_parser()

    def _uses_template_layout(self) -> bool:
        use_template_layout = getattr(self.help_layout, "_use_template_layout", None)
        if not callable(use_template_layout):
            return False
        return bool(use_template_layout())

    @staticmethod
    def _escape_argparse_help_text(text: str | None) -> str:
        if not text or "%" not in text:
            return text or ""
        return text.replace("%", "%%")

    @staticmethod
    def _normalize_boolean_optional_flags(flags: tuple[str, ...]) -> tuple[str, ...]:
        """
        Normalize bool option strings for ``BooleanOptionalAction`` compatibility.

        Python 3.14 rejects ``BooleanOptionalAction`` when all long flags already
        start with ``--no-``. In that case, derive a positive base flag from the
        first long option (e.g. ``--no-tokens`` -> ``--tokens``) and let argparse
        generate the negative alias.
        """
        long_flags = [flag for flag in flags if flag.startswith("--")]
        if not long_flags:
            return flags
        if any(not flag.startswith("--no-") for flag in long_flags):
            return flags

        normalized: list[str] = []
        replaced = False
        for flag in flags:
            if not replaced and flag.startswith("--no-") and len(flag) > len("--no-"):
                normalized.append(f"--{flag[len('--no-') :]}")
                replaced = True
            else:
                normalized.append(flag)
        return tuple(normalized)

    def _parameter_help(self, param: Parameter, flags: tuple[str, ...]) -> str:
        if self._uses_template_layout():
            return self.help_layout.get_help_for_parameter(param, None)
        help_text = self.help_layout.get_help_for_parameter(param, flags)
        return self._escape_argparse_help_text(help_text)

    @staticmethod
    def _resolve_list_annotation(annotation: object | None) -> tuple[object | None, object | None]:
        optional_union_list = extract_optional_union_list(annotation)
        if optional_union_list:
            return optional_union_list
        if annotation is not None and is_list_or_list_alias(annotation):
            list_args = type_args(annotation)
            return annotation, (list_args[0] if list_args else None)
        return None, None

    def _apply_typed_argument_params(
        self, extra: dict[str, Any], param: Parameter, annotation: object
    ) -> None:
        list_annotation, element_type = self._resolve_list_annotation(annotation)
        if list_annotation is not None:
            extra["nargs"] = "*"
            if element_type is not None:
                extra["type"] = self.type_parser.get_parse_func(element_type)
        else:
            extra["type"] = self.type_parser.get_parse_func(annotation)

        choices = get_param_choices(param, for_display=False)
        if choices:
            extra["choices"] = self._coerce_choices_for_parser(choices, extra.get("type"))

    @staticmethod
    def _is_positional_flags(flags: tuple[str, ...]) -> bool:
        return all(not flag.startswith("-") for flag in flags)

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
        extra: dict[str, Any] = {"help": self._parameter_help(param, flags)}

        annotation = resolve_type_alias(param.type) if param.is_typed else None
        is_bool_param = param.is_typed and annotation is bool
        if param.is_typed and not is_bool_param:
            self._apply_typed_argument_params(extra, param, annotation)

        if self.help_layout.clear_metavar and not is_bool_param and not param.is_required:
            extra["metavar"] = "\b"

        is_positional = self._is_positional_flags(flags)
        logger.debug("Flags: %s, positional=%s", flags, is_positional)
        if not is_positional:
            extra["required"] = param.is_required

        if is_bool_param:
            extra["action"] = argparse.BooleanOptionalAction
            extra["default"] = param.default if not param.is_required else False
            return extra

        if not param.is_required:
            extra["default"] = param.default
        return extra

    def _argument_kwargs(self, arg: Argument) -> dict[str, Any]:
        help_text = arg.help or ""
        if not self._uses_template_layout():
            help_text = self.help_layout.format_argument(arg)
            help_text = self._escape_argparse_help_text(help_text)

        kwargs: dict[str, Any] = {"help": help_text}
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

        if arg.kind == ArgumentKind.OPTION:
            kwargs["required"] = arg.required

        return kwargs

    def _add_argument_from_schema(self, parser: ArgumentParser, argument: Argument) -> None:
        kwargs = self._argument_kwargs(argument)
        add_flags = argument.flags
        if kwargs.get("action") is argparse.BooleanOptionalAction:
            add_flags = self._normalize_boolean_optional_flags(argument.flags)
        logger.info("Adding argument flags=%s, kwargs=%s", add_flags, kwargs)
        parser.add_argument(*add_flags, **kwargs)

    @staticmethod
    def _coerce_choices_for_parser(
        choices: Sequence[Any] | None, parser: Callable[[str], Any] | None
    ) -> Sequence[Any] | None:
        if not choices or parser is None:
            return choices
        if not all(isinstance(choice, str) for choice in choices):
            return choices

        try:
            return [parser(choice) for choice in choices]
        except (argparse.ArgumentTypeError, TypeError, ValueError):
            return choices

    @staticmethod
    def _set_subparsers_metavar(subparsers: NestedSubParsersAction) -> None:
        names: list[str] = []
        seen_parsers: set[int] = set()
        for name, parser in subparsers.choices.items():
            parser_id = id(parser)
            if parser_id in seen_parsers:
                continue
            seen_parsers.add(parser_id)
            names.append(name)
        if names:
            subparsers.metavar = "{" + ",".join(names) + "}"

    @staticmethod
    def _is_legacy_commands_epilog(text: str | None) -> bool:
        if not text:
            return False
        normalized = re.sub(r"\x1b\[[0-9;]*m", "", text)
        return normalized.lstrip().lower().startswith("commands:")

    def _use_native_subparser_help(self) -> bool:
        return not self._uses_template_layout()

    def _subparsers_title(self) -> str | None:
        if not self._use_native_subparser_help():
            return None
        return "commands"

    def _should_set_epilog(self, epilog: str | None) -> bool:
        if not epilog:
            return False
        return not (self._use_native_subparser_help() and self._is_legacy_commands_epilog(epilog))

    def _command_dest(self, depth: int) -> str:
        return f"{self.COMMAND_KEY}_{depth}" if depth > 0 else self.COMMAND_KEY

    def _ordered_arguments_for_help(self, arguments: Sequence[Argument]) -> list[Argument]:
        if not arguments:
            return []

        positionals = [arg for arg in arguments if arg.kind == ArgumentKind.POSITIONAL]
        options = [arg for arg in arguments if arg.kind == ArgumentKind.OPTION]
        ordered_options = self.help_layout.order_option_arguments_for_help(options)
        return [*positionals, *ordered_options]

    def _add_initializer_arguments(self, parser: ArgumentParser, command: Command) -> None:
        for argument in self._ordered_arguments_for_help(command.initializer):
            self._add_argument_from_schema(parser, argument)

    def _add_parameter_arguments(self, parser: ArgumentParser, command: Command) -> None:
        for argument in self._ordered_arguments_for_help(command.parameters):
            self._add_argument_from_schema(parser, argument)

    def _create_command_subparsers(
        self,
        parser: ArgumentParser,
        *,
        depth: int,
        has_custom_epilog: bool,
    ) -> NestedSubParsersAction:
        return parser.add_subparsers(
            dest=self._command_dest(depth),
            required=True,
            title=self._subparsers_title(),
            help=(
                argparse.SUPPRESS
                if has_custom_epilog and not self._use_native_subparser_help()
                else None
            ),
        )

    def _add_subcommands(
        self,
        subparsers: NestedSubParsersAction,
        command: Command,
        *,
        depth: int,
        include_aliases: bool,
    ) -> None:
        if not command.subcommands:
            return
        for sub_cmd in command.subcommands.values():
            parser_kwargs: dict[str, Any] = {
                "description": sub_cmd.description,
                "help": self._escape_argparse_help_text(sub_cmd.description),
            }
            if include_aliases:
                parser_kwargs["aliases"] = list(sub_cmd.aliases) if sub_cmd.aliases else []
            subparser = subparsers.add_parser(sub_cmd.cli_name, **parser_kwargs)
            self._apply_command_schema(subparser, sub_cmd, depth=depth + 1)

    def _apply_schema_for_subcommands(
        self,
        parser: ArgumentParser,
        command: Command,
        *,
        depth: int,
        include_aliases: bool,
    ) -> None:
        self._add_initializer_arguments(parser, command)
        if self._should_set_epilog(command.epilog):
            parser.epilog = command.epilog
        subparsers = self._create_command_subparsers(
            parser,
            depth=depth,
            has_custom_epilog=bool(command.epilog),
        )
        self._add_subcommands(
            subparsers,
            command,
            depth=depth,
            include_aliases=include_aliases,
        )
        self._set_subparsers_metavar(subparsers)

    def _apply_command_schema(
        self,
        parser: ArgumentParser,
        command: Command,
        *,
        depth: int = 0,
    ) -> None:
        parser.set_schema_command(command)

        if command.description:
            parser.description = command.description

        if not command.is_leaf and command.subcommands:
            self._apply_schema_for_subcommands(
                parser,
                command,
                depth=depth,
                include_aliases=True,
            )
            return

        if isinstance(command.obj, Class):
            self._apply_schema_for_subcommands(
                parser,
                command,
                depth=depth,
                include_aliases=False,
            )
            return

        if isinstance(command.obj, Method):
            self._add_initializer_arguments(parser, command)

        self._add_parameter_arguments(parser, command)

    def _build_from_schema(self, schema: ParserSchema) -> ArgumentParser:
        parser = self._new_parser()
        parser.set_schema(schema)

        single_cmd = next(iter(schema.commands.values())) if len(schema.commands) == 1 else None
        single_group = single_cmd if single_cmd and not single_cmd.is_leaf else None

        if schema.is_multi_command or single_group:
            subparsers = parser.add_subparsers(
                dest=self.COMMAND_KEY,
                required=True,
                title=self._subparsers_title(),
                help=(
                    argparse.SUPPRESS
                    if schema.commands_help and not self._use_native_subparser_help()
                    else None
                ),
            )
            for cmd in schema.commands.values():
                subparser = subparsers.add_parser(
                    cmd.cli_name,
                    description=cmd.description,
                    help=self._escape_argparse_help_text(cmd.description),
                    aliases=list(cmd.aliases),
                )
                self._apply_command_schema(subparser, cmd)
            self._set_subparsers_metavar(subparsers)

            if schema.commands_help and not (
                self._use_native_subparser_help()
                and self._is_legacy_commands_epilog(schema.commands_help)
            ):
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
        """Build and return an ArgumentParser from the current commands."""
        if not self.commands:
            raise ConfigurationError("No commands were provided")

        schema = self.build_parser_schema()
        self._last_schema = schema
        parser = self._build_from_schema(schema)

        if self.enable_tab_completion:
            self.install_tab_completion(parser)
        return parser

    def get_last_schema(self) -> ParserSchema | None:
        """Return the most recently built parser schema for this backend."""
        return self._last_schema

    def parse_args(self, args: list[str] | None = None) -> dict[str, Any]:
        """
        Parse CLI args into a nested dict keyed by command name.

        Args:
            args (list[str] | None): Argument list to parse. Defaults to sys.argv.
        """
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
        schema = self._last_schema or self.build_parser_schema()
        for command in schema.commands.values():
            self._convert_command_tuple_arguments(command, namespace)

        return namespace

    @staticmethod
    def _tuple_value(argument: Argument, value: list[Any]) -> tuple[Any, ...]:
        if argument.tuple_element_parsers:
            return tuple(
                parser(item)
                for parser, item in zip(argument.tuple_element_parsers, value, strict=False)
            )
        return tuple(value)

    def _convert_tuple_values_for_arguments(
        self, arguments: Sequence[Argument], namespace: dict[str, Any]
    ) -> None:
        for argument in arguments:
            if argument.value_shape != ValueShape.TUPLE:
                continue
            value = namespace.get(argument.name)
            if isinstance(value, list):
                namespace[argument.name] = self._tuple_value(argument, value)

    def _convert_command_tuple_arguments(self, command: Command, namespace: dict[str, Any]) -> None:
        self._convert_tuple_values_for_arguments(command.initializer, namespace)
        self._convert_tuple_values_for_arguments(command.parameters, namespace)
        if not command.subcommands:
            return

        for subcommand in command.subcommands.values():
            sub_namespace = namespace.get(subcommand.cli_name)
            if isinstance(sub_namespace, dict):
                self._convert_command_tuple_arguments(subcommand, sub_namespace)

    def _handle_interrupt(self, exc: KeyboardInterrupt) -> KeyboardInterrupt:
        """Handle KeyboardInterrupt with callback, logging, and optional re-raise."""
        if self.on_interrupt is not None:
            self.on_interrupt(exc)
        self.log_interrupt()
        self.exit(ExitCode.INTERRUPTED)
        if self.reraise_interrupt:
            raise exc
        return exc

    def _install_sigint_handler(
        self,
    ) -> tuple[Any, Callable[[int, FrameType | None], None]]:
        original_handler = signal.getsignal(signal.SIGINT)

        def sigint_handler(_signum: int, _frame: FrameType | None) -> None:
            now = time.time()
            if now - self._last_interrupt_time < 1.0:  # Double Ctrl+C: force immediate exit
                sys.exit(ExitCode.INTERRUPTED)
            self._last_interrupt_time = now
            raise KeyboardInterrupt()

        signal.signal(signal.SIGINT, sigint_handler)
        return original_handler, sigint_handler

    def _parse_run_input(
        self,
        commands: Sequence[Callable[..., Any] | type | object],
        args: list[str] | None,
    ) -> tuple[list[str], dict[str, Any]] | BaseException:
        try:
            self.reset_piped_input()
            for command in commands:
                self.add_command(command, name=None, description=None)

            resolved_args = args if args is not None else self.get_args()
            logger.info("Got args: %s", resolved_args)
            namespace = self.parse_args(resolved_args)
        except (
            DuplicateCommandError,
            UnsupportedParameterTypeError,
            ReservedFlagError,
            InvalidCommandError,
            ConfigurationError,
        ) as exc:
            self.log_exception(exc)
            self.exit(ExitCode.ERR_PARSING)
            return exc
        except SystemExit as exc:
            if self.sys_exit_enabled:
                raise
            return exc
        except KeyboardInterrupt as exc:
            return self._handle_interrupt(exc)
        else:
            return resolved_args, namespace

    def _run_runner(self, namespace: dict[str, Any], args: list[str]) -> object | BaseException:
        if self._parser is None:
            raise RuntimeError("Parser not initialized")
        try:
            runner = ArgparseRunner(
                namespace=namespace,
                args=args,
                parser=self._parser,
                builder=self,
            )
            return runner.run()
        except InterfacyError as exc:
            self.log_exception(exc)
            self.exit(ExitCode.ERR_RUNTIME_INTERNAL)
            return exc
        except SystemExit as exc:
            if self.sys_exit_enabled:
                raise
            return exc
        except KeyboardInterrupt as exc:
            return self._handle_interrupt(exc)
        except Exception as exc:  # noqa: BLE001 - CLI boundary catches user command errors
            self.log_exception(exc)
            self.exit(ExitCode.ERR_RUNTIME)
            return exc

    @staticmethod
    def _is_exception_result(value: object) -> bool:
        return isinstance(value, BaseException)

    def run(
        self, *commands: Callable[..., Any] | type | object, args: list[str] | None = None
    ) -> object:
        """
        Register commands, parse args, and execute the selected command.

        Args:
            *commands (Callable[..., Any] | type | object): Commands to register.
            args (list[str] | None): Argument list to parse. Defaults to sys.argv.
        """
        original_handler, sigint_handler = self._install_sigint_handler()
        try:
            parse_result = self._parse_run_input(commands, args)
        finally:
            signal.signal(signal.SIGINT, original_handler)

        if self._is_exception_result(parse_result):
            return parse_result
        resolved_args, namespace = parse_result

        signal.signal(signal.SIGINT, sigint_handler)
        try:
            result = self._run_runner(namespace, resolved_args)
        finally:
            signal.signal(signal.SIGINT, original_handler)

        if self._is_exception_result(result):
            return result

        if self.display_result:
            self.result_display_fn(result)

        self.exit(ExitCode.SUCCESS)
        return result


__all__ = ["Argparser"]

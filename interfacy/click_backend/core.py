from __future__ import annotations

import argparse
import signal
import sys
import time
from collections.abc import Callable, Sequence
from typing import Any, ClassVar

try:
    import click
    from click.core import ParameterSource
except ModuleNotFoundError as exc:  # pragma: no cover - handled by optional dependency guard
    raise ImportError(
        "Click is required to use ClickParser. Install it with "
        "\"pip install 'interfacy[click]'\" or \"uv add 'interfacy[click]'\"."
    ) from exc

from objinspect import Class

from interfacy.appearance.layout import HelpLayout, InterfacyColors
from interfacy.click_backend.commands import (
    InterfacyClickArgument,
    InterfacyClickCommand,
    InterfacyClickGroup,
    InterfacyClickOption,
    InterfacyListOption,
)
from interfacy.click_backend.types import ChoiceParamType, ClickFuncParamType
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
from interfacy.runner import SchemaRunner
from interfacy.schema.schema import Argument, ArgumentKind, Command, ParserSchema, ValueShape

logger = get_logger(__name__)


class ClickParser(InterfacyParser):
    RESERVED_FLAGS: ClassVar[list[str]] = ["help"]

    def __init__(
        self,
        description: str | None = None,
        epilog: str | None = None,
        type_parser: Any | None = None,
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
        print_result_func: Callable[[Any], Any] = print,
        include_inherited_methods: bool = False,
        include_classmethods: bool = False,
        expand_model_params: bool = True,
        model_expansion_max_depth: int = 3,
    ) -> None:
        super().__init__(
            description,
            epilog,
            help_layout,
            type_parser,
            help_colors=help_colors,
            pipe_targets=pipe_targets,
            allow_args_from_file=allow_args_from_file,
            print_result=print_result,
            print_result_func=print_result_func,
            flag_strategy=flag_strategy,
            tab_completion=tab_completion,
            abbreviation_gen=abbreviation_gen,
            include_inherited_methods=include_inherited_methods,
            include_classmethods=include_classmethods,
            full_error_traceback=full_error_traceback,
            sys_exit_enabled=sys_exit_enabled,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=model_expansion_max_depth,
        )
        if list in self.type_parser.parsers:
            del self.type_parser.parsers[list]
        self._last_schema: ParserSchema | None = None
        self._root_command: click.Command | None = None
        self._last_interrupt_time: float = 0.0

    def _command_key_for_depth(self, depth: int) -> str:
        return f"{self.COMMAND_KEY}_{depth}" if depth > 0 else self.COMMAND_KEY

    def _remaining_args(self, ctx: click.Context) -> list[str]:
        protected = getattr(ctx, "_protected_args", None)
        if protected:
            return [*protected, *ctx.args]
        return list(ctx.args)

    def _choice_type(self, argument: Argument) -> click.ParamType | None:
        if not argument.choices:
            return None
        if argument.parser is not None:
            return ChoiceParamType(argument.choices, argument.parser)
        if all(isinstance(choice, str) for choice in argument.choices):
            return click.Choice([str(choice) for choice in argument.choices], case_sensitive=True)
        return ChoiceParamType(argument.choices, None)

    def _param_type(self, argument: Argument) -> click.ParamType | None:
        choice_type = self._choice_type(argument)
        if choice_type is not None:
            return choice_type
        if argument.parser is not None:
            return ClickFuncParamType(argument.parser, f"parse_{argument.name}")
        return None

    def _sanitize_param_name(self, name: str, used: set[str]) -> str:
        cleaned = name.replace("-", "_").replace(".", "_").replace(" ", "_")
        if not cleaned.isidentifier():
            cleaned = "param"
        candidate = cleaned
        counter = 1
        while candidate in used:
            candidate = f"{cleaned}_{counter}"
            counter += 1
        used.add(candidate)
        return candidate

    def _argument_default(self, argument: Argument) -> tuple[Any, bool]:
        default = argument.default
        if argument.value_shape == ValueShape.FLAG and argument.boolean_behavior is not None:
            default = argument.boolean_behavior.default
        suppress = default is argparse.SUPPRESS
        if suppress:
            default = None
        return default, suppress

    def _make_click_param(
        self,
        argument: Argument,
        used_names: set[str],
    ) -> tuple[click.Parameter, bool]:
        param_type = None if argument.value_shape == ValueShape.FLAG else self._param_type(argument)
        default, suppress = self._argument_default(argument)
        param: click.Parameter

        if argument.kind == ArgumentKind.POSITIONAL:
            nargs = None
            if argument.value_shape == ValueShape.LIST:
                nargs = -1
            elif argument.value_shape == ValueShape.TUPLE and isinstance(argument.nargs, int):
                nargs = argument.nargs

            attrs: dict[str, Any] = {
                "required": argument.required,
                "help": argument.help,
            }
            if argument.metavar and argument.value_shape != ValueShape.FLAG:
                attrs["metavar"] = argument.metavar
            if nargs is not None:
                attrs["nargs"] = nargs
            if param_type is not None:
                attrs["type"] = param_type
            if nargs != -1 and not suppress:
                attrs["default"] = default

            param = InterfacyClickArgument((argument.display_name,), **attrs)
            return param, suppress

        param_name = self._sanitize_param_name(argument.name, used_names)

        if argument.value_shape == ValueShape.FLAG and argument.boolean_behavior is not None:
            param_decls: list[str] = [param_name]
            long_flags = [flag for flag in argument.flags if flag.startswith("--")]
            short_flags = [
                flag
                for flag in argument.flags
                if flag.startswith("-") and not flag.startswith("--")
            ]
            if argument.boolean_behavior.supports_negative and long_flags:
                positive = long_flags[0]
                negative = argument.boolean_behavior.negative_form or ""
                combined = f"{positive}/{negative}" if negative else positive
                if short_flags:
                    param_decls.extend(short_flags)
                param_decls.append(combined)
            else:
                param_decls.extend(argument.flags)

            attrs = {
                "is_flag": True,
                "help": argument.help,
                "required": argument.required,
            }
            if not argument.boolean_behavior.supports_negative:
                attrs["flag_value"] = True
            if not suppress:
                attrs["default"] = default
            param = InterfacyClickOption(param_decls, **attrs)
            return param, suppress

        attrs = {
            "help": argument.help,
            "required": argument.required,
        }
        if argument.metavar and argument.value_shape != ValueShape.FLAG:
            attrs["metavar"] = argument.metavar

        if param_type is not None:
            attrs["type"] = param_type

        if argument.value_shape == ValueShape.LIST:
            if not suppress:
                attrs["default"] = default
            param = InterfacyListOption([param_name, *argument.flags], **attrs)
            return param, suppress

        if argument.value_shape == ValueShape.TUPLE and isinstance(argument.nargs, int):
            attrs["nargs"] = argument.nargs

        if not suppress:
            attrs["default"] = default

        param = InterfacyClickOption([param_name, *argument.flags], **attrs)
        return param, suppress

    def _build_click_params(
        self, arguments: list[Argument]
    ) -> tuple[list[click.Parameter], dict[str, str], dict[str, Argument], set[str]]:
        params: list[click.Parameter] = []
        param_bindings: dict[str, str] = {}
        arg_specs: dict[str, Argument] = {}
        suppress_defaults: set[str] = set()
        used_names: set[str] = set()

        for argument in arguments:
            param, suppress = self._make_click_param(argument, used_names)
            params.append(param)
            if param.name is not None:
                param_bindings[param.name] = argument.name
            arg_specs[argument.name] = argument
            if suppress:
                suppress_defaults.add(argument.name)

        return params, param_bindings, arg_specs, suppress_defaults

    def _attach_param_metadata(
        self,
        command: InterfacyClickCommand | InterfacyClickGroup,
        param_bindings: dict[str, str],
        arg_specs: dict[str, Argument],
        suppress_defaults: set[str],
        schema: Command,
    ) -> None:
        command._interfacy_param_bindings = param_bindings
        command._interfacy_arg_specs = arg_specs
        command._interfacy_suppress_defaults = suppress_defaults
        command._interfacy_schema = schema
        command._interfacy_aliases = schema.aliases
        command._interfacy_epilog = schema.epilog

    def build_click_command(
        self, command: Command, depth: int = 0
    ) -> InterfacyClickCommand | InterfacyClickGroup:
        is_group_like = (
            command.command_type in ("group", "instance")
            or command.subcommands is not None
            or isinstance(command.obj, Class)
        )
        if not is_group_like:
            params, param_bindings, arg_specs, suppress_defaults = self._build_click_params(
                command.parameters
            )
            click_command = InterfacyClickCommand(
                name=command.cli_name,
                help=command.description,
                params=params,
            )
            self._attach_param_metadata(
                click_command, param_bindings, arg_specs, suppress_defaults, command
            )
            return click_command

        params, param_bindings, arg_specs, suppress_defaults = self._build_click_params(
            command.initializer
        )
        group = InterfacyClickGroup(
            name=command.cli_name,
            help=command.description,
            params=params,
            context_settings={"allow_interspersed_args": False},
        )
        self._attach_param_metadata(group, param_bindings, arg_specs, suppress_defaults, command)

        if command.subcommands:
            for subcommand in command.subcommands.values():
                group.add_command(
                    self.build_click_command(subcommand, depth + 1), name=subcommand.cli_name
                )
        return group

    def _combine_epilog(self, *parts: str | None) -> str | None:
        chunks = [part for part in parts if part]
        if not chunks:
            return None
        return "\n\n".join(chunks)

    def _is_class_command(self, command: Command | None) -> bool:
        if command is None:
            return False
        return isinstance(command.obj, Class)

    def _build_from_schema(self, schema: ParserSchema) -> click.Command:
        single_cmd = next(iter(schema.commands.values())) if len(schema.commands) == 1 else None
        single_group = (
            single_cmd
            if single_cmd and not single_cmd.is_leaf and not self._is_class_command(single_cmd)
            else None
        )

        if schema.is_multi_command or single_group:
            root = InterfacyClickGroup(name="main", help=schema.description)
            root.context_settings.setdefault("allow_interspersed_args", False)
            root._interfacy_is_root = True
            root._interfacy_parser_schema = schema
            root._interfacy_epilog = self._combine_epilog(schema.commands_help, schema.epilog)

            for cmd in schema.commands.values():
                root.add_command(self.build_click_command(cmd), name=cmd.cli_name)
            return root

        cmd = next(iter(schema.commands.values()))
        click_command = self.build_click_command(cmd)
        click_command._interfacy_epilog = self._combine_epilog(cmd.epilog, schema.epilog)
        return click_command

    def build_parser(self) -> click.Command:
        """Build and return a Click command tree from the current commands."""
        if not self.commands:
            raise ConfigurationError("No commands were provided")

        schema = self.build_parser_schema()
        self._last_schema = schema
        root = self._build_from_schema(schema)
        self._root_command = root
        if self.enable_tab_completion:
            self.install_tab_completion(root)
        return root

    def _params_to_schema(
        self,
        ctx: click.Context,
        command: InterfacyClickCommand | InterfacyClickGroup,
    ) -> dict[str, Any]:
        bindings = command._interfacy_param_bindings
        suppress_defaults = command._interfacy_suppress_defaults
        params: dict[str, Any] = {}

        for click_name, value in ctx.params.items():
            schema_name = bindings.get(click_name, click_name)
            if schema_name in suppress_defaults:
                source = ctx.get_parameter_source(click_name)
                if source in (ParameterSource.DEFAULT, ParameterSource.DEFAULT_MAP, None):
                    continue
            params[schema_name] = value
        return params

    def _build_namespace_for_ctx(
        self,
        ctx: click.Context,
        command: InterfacyClickCommand | InterfacyClickGroup,
        depth: int,
    ) -> dict[str, Any]:
        namespace = self._params_to_schema(ctx, command)

        if isinstance(command, click.Group) and command.commands:
            combined_args = self._remaining_args(ctx)
            cmd_name, sub_cmd, remaining = command.resolve_command(ctx, combined_args)
            if not isinstance(sub_cmd, (InterfacyClickCommand, InterfacyClickGroup)):
                raise ConfigurationError(f"Unexpected command type from click: {type(sub_cmd)!r}")
            resolved_cmd_name = cmd_name if cmd_name is not None else (sub_cmd.name or "")
            sub_ctx = sub_cmd.make_context(
                resolved_cmd_name, remaining, parent=ctx, resilient_parsing=False
            )
            dest_key = self._command_key_for_depth(depth)
            namespace[dest_key] = resolved_cmd_name
            sub_cli_name = sub_cmd._interfacy_schema
            fallback_sub_name = sub_cmd.name if sub_cmd.name is not None else resolved_cmd_name
            sub_key = sub_cli_name.cli_name if sub_cli_name is not None else fallback_sub_name
            namespace[sub_key] = self._build_namespace_for_ctx(sub_ctx, sub_cmd, depth + 1)

        return namespace

    def _normalize_parsed_args(self, namespace: dict[str, Any]) -> dict[str, Any]:
        schema = self._last_schema or self.build_parser_schema()

        def convert_tuple(arg: Argument, val: Sequence[Any]) -> tuple[Any, ...]:
            if arg.tuple_element_parsers:
                return tuple(
                    parser(v) for parser, v in zip(arg.tuple_element_parsers, val, strict=False)
                )
            return tuple(val)

        def normalize_arg(arg: Argument, bucket: dict[str, Any]) -> None:
            if arg.name not in bucket:
                return
            val = bucket[arg.name]
            if arg.value_shape == ValueShape.TUPLE and isinstance(val, (list, tuple)):
                bucket[arg.name] = convert_tuple(arg, val)
            elif arg.value_shape == ValueShape.LIST and isinstance(val, tuple):
                bucket[arg.name] = list(val)

        def normalize_command(command: Command, bucket: dict[str, Any]) -> None:
            for arg in command.initializer:
                normalize_arg(arg, bucket)
            for arg in command.parameters:
                normalize_arg(arg, bucket)
            if command.subcommands:
                for sub_cmd in command.subcommands.values():
                    sub_bucket = bucket.get(sub_cmd.cli_name)
                    if isinstance(sub_bucket, dict):
                        normalize_command(sub_cmd, sub_bucket)

        single_cmd = next(iter(schema.commands.values())) if len(schema.commands) == 1 else None
        if single_cmd and not schema.is_multi_command and single_cmd.is_leaf:
            normalize_command(single_cmd, namespace)
            return namespace

        for cmd in schema.commands.values():
            bucket = namespace.get(cmd.cli_name)
            if isinstance(bucket, dict):
                normalize_command(cmd, bucket)
        return namespace

    def parse_args(self, args: list[str] | None = None) -> dict[str, Any]:
        """
        Parse CLI args into a nested dict keyed by command name.

        Args:
            args (list[str] | None): Argument list to parse. Defaults to sys.argv.
        """
        args = args if args is not None else self.get_args()
        root = self.build_parser()

        if isinstance(root, InterfacyClickGroup) and root._interfacy_is_root:
            ctx = root.make_context(root.name or "main", args, resilient_parsing=False)
            combined_args = self._remaining_args(ctx)
            cmd_name, cmd, remaining = root.resolve_command(ctx, combined_args)
            if not isinstance(cmd, (InterfacyClickCommand, InterfacyClickGroup)):
                raise ConfigurationError(f"Unexpected command type from click: {type(cmd)!r}")
            resolved_cmd_name = cmd_name if cmd_name is not None else (cmd.name or "")
            sub_ctx = cmd.make_context(
                resolved_cmd_name, remaining, parent=ctx, resilient_parsing=False
            )
            schema_cmd = cmd._interfacy_schema
            top_cli_name = schema_cmd.cli_name if schema_cmd is not None else resolved_cmd_name
            namespace = {
                self.COMMAND_KEY: top_cli_name,
                top_cli_name: self._build_namespace_for_ctx(sub_ctx, cmd, depth=0),
            }
            return self._normalize_parsed_args(namespace)

        ctx = root.make_context(root.name or "main", args, resilient_parsing=False)
        if not isinstance(root, (InterfacyClickCommand, InterfacyClickGroup)):
            raise ConfigurationError(f"Unexpected root command type: {type(root)!r}")
        namespace = self._build_namespace_for_ctx(ctx, root, depth=0)
        return self._normalize_parsed_args(namespace)

    def _handle_interrupt(self, exc: KeyboardInterrupt) -> KeyboardInterrupt:
        if self.on_interrupt is not None:
            self.on_interrupt(exc)
        self.log_interrupt()
        self.exit(ExitCode.INTERRUPTED)
        if self.reraise_interrupt:
            raise exc
        return exc

    def run(self, *commands: Callable[..., Any], args: list[str] | None = None) -> Any:
        """
        Register commands, parse args, and execute the selected command.

        Args:
            *commands (Callable[..., Any]): Commands to register.
            args (list[str] | None): Argument list to parse. Defaults to sys.argv.
        """
        original_handler = signal.getsignal(signal.SIGINT)

        def sigint_handler(signum: int, frame: Any) -> None:
            now = time.time()
            if now - self._last_interrupt_time < 1.0:
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
            click.UsageError,
        ) as e:
            if isinstance(e, click.exceptions.NoArgsIsHelpError):
                err = ConfigurationError(str(e))
                self.log_exception(err)
                self.exit(ExitCode.ERR_PARSING)
                return err
            self.log_exception(e)
            self.exit(ExitCode.ERR_PARSING)
            return e
        except click.exceptions.Exit as e:
            system_exit = SystemExit(e.exit_code)
            if self.sys_exit_enabled:
                raise system_exit
            return system_exit
        except SystemExit as e:
            if self.sys_exit_enabled:
                raise
            return e
        except KeyboardInterrupt as e:
            return self._handle_interrupt(e)
        finally:
            signal.signal(signal.SIGINT, original_handler)

        signal.signal(signal.SIGINT, sigint_handler)
        try:
            runner = SchemaRunner(
                namespace=namespace,
                args=args,
                builder=self,
            )
            result = runner.run()
        except InterfacyError as e:
            self.log_exception(e)
            self.exit(ExitCode.ERR_RUNTIME_INTERNAL)
            return e
        except click.exceptions.Exit as e:
            system_exit = SystemExit(e.exit_code)
            if self.sys_exit_enabled:
                raise system_exit
            return system_exit
        except SystemExit as e:
            if self.sys_exit_enabled:
                raise
            return e
        except click.UsageError as e:
            self.log_exception(e)
            self.exit(ExitCode.ERR_PARSING)
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

    def parser_from_function(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("ClickParser builds commands from ParserSchema only.")

    def parser_from_class(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("ClickParser builds commands from ParserSchema only.")

    def parser_from_multiple_commands(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("ClickParser builds commands from ParserSchema only.")

    def install_tab_completion(self, *args: Any, **kwargs: Any) -> None:
        return None


__all__ = ["ClickParser"]

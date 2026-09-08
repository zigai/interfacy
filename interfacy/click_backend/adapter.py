from __future__ import annotations

import warnings
from collections.abc import Mapping, Sequence
from typing import Any, NoReturn

import click
from click.core import ParameterSource

from interfacy.click_backend.commands import (
    InterfacyBooleanOption,
    InterfacyClickArgument,
    InterfacyClickCommand,
    InterfacyClickGroup,
    InterfacyClickOption,
    InterfacyListOption,
)
from interfacy.click_backend.types import ChoiceParamType, ClickFuncParamType
from interfacy.engine.backend import (
    BackendConfig,
    BackendParseFailure,
    BackendSession,
    HelpPipeline,
    NativePresentation,
    ParseOutcome,
    ParseRequest,
    ParseResult,
)
from interfacy.engine.settings import BackendName
from interfacy.exceptions import ConfigurationError, InterfacyExit, UsageError
from interfacy.executable_flag import ExecutableAction, ExecutableFlag
from interfacy.schema.schema import Argument, ArgumentKind, Command, ParserSchema, ValueShape
from interfacy.schema.value_plan import normalize_schema_values

_COMMAND_KEY = "command"


class _ExecutableFlagTriggeredError(Exception):
    def __init__(self, flag: ExecutableFlag) -> None:
        self.flag = flag
        super().__init__(flag.flags[0])


class ClickSession(BackendSession[click.Command]):
    def __init__(
        self,
        schema: ParserSchema,
        help_pipeline: HelpPipeline,
        config: BackendConfig,
    ) -> None:
        self._schema = schema
        self._help_pipeline = help_pipeline
        self._config = config
        self._native_parser = self._build(schema, relaxed=False)
        self._partial_parser: click.Command | None = None
        self._attach_help(self._native_parser, ())

    @property
    def native_parser(self) -> click.Command:
        return self._native_parser

    def parse(self, request: ParseRequest) -> ParseOutcome:
        root = self._parser_for(request)
        try:
            namespace, remaining = self._parse_root(
                root,
                list(request.args),
                partial=request.mode == "partial",
                include_defaults=request.default_policy == "include",
            )
            normalize_schema_values(self._schema, namespace, type_parser=self._config.type_parser)
            return ParseResult(request.args, namespace, tuple(remaining))
        except _ExecutableFlagTriggeredError as e:
            return ExecutableAction(e.flag)
        except click.exceptions.Exit as e:
            raise InterfacyExit(e.exit_code) from e
        except click.UsageError as e:
            partial = self._partial_namespace(request.args)
            message = e.format_message()
            return BackendParseFailure(
                request=request,
                presentation=NativePresentation(
                    kind="usage",
                    message=message,
                    exit_code=e.exit_code,
                ),
                partial_namespace=partial,
            )
        except ValueError as e:
            return BackendParseFailure(
                request=request,
                presentation=NativePresentation(
                    kind="usage",
                    message=str(e),
                    exit_code=2,
                ),
                partial_namespace=self._partial_namespace(request.args),
            )

    def present_error(self, presentation: NativePresentation) -> NoReturn:
        usage = None
        if presentation.kind == "usage":
            usage = self._native_parser.get_usage(click.Context(self._native_parser))

        raise UsageError(presentation.message, usage=usage)

    def _attach_help(
        self,
        command: click.Command,
        command_path: tuple[str, ...],
    ) -> None:
        if isinstance(command, (InterfacyClickCommand, InterfacyClickGroup)):
            command.set_help_pipeline(self._help_pipeline, command_path)

        if not isinstance(command, click.Group):
            return

        seen: set[int] = set()
        for name, child in command.commands.items():
            if id(child) in seen:
                continue

            seen.add(id(child))
            schema_command = getattr(child, "interfacy_schema", None)
            canonical = (
                schema_command.canonical_name if isinstance(schema_command, Command) else name
            )
            self._attach_help(child, (*command_path, canonical))

    def _parser_for(self, request: ParseRequest) -> click.Command:
        if request.mode == "full":
            return self._native_parser

        if self._partial_parser is None:
            self._partial_parser = self._build(self._schema, relaxed=True)

        return self._partial_parser

    def _build(self, schema: ParserSchema, *, relaxed: bool) -> click.Command:
        commands = list(schema.commands.values())
        single = commands[0] if len(commands) == 1 else None
        root_group = schema.is_multi_command or (
            single is not None and single.command_type == "group" and not single.is_leaf
        )
        if not root_group:
            if single is None:
                raise ConfigurationError("No commands were provided")

            root = self._build_command(
                single,
                relaxed=relaxed,
                extra_flags=schema.executable_flags,
            )
            root.interfacy_parser_schema = schema
            root.interfacy_help_layout = self._config.help_layout

            return root

        params, bindings, specs, suppressed = self._build_params(
            (),
            schema.executable_flags,
            relaxed=relaxed,
        )
        root = InterfacyClickGroup(
            name=self._config.program_name or "main",
            help=schema.description,
            params=params,
            context_settings={
                "help_option_names": list(self._config.help_flags),
                "allow_interspersed_args": False,
            },
            invoke_without_command=relaxed,
            no_args_is_help=not relaxed,
        )
        self._attach(root, bindings, specs, suppressed, None)
        root.interfacy_is_root = True
        root.interfacy_parser_schema = schema
        root.interfacy_help_layout = self._config.help_layout

        for command in commands:
            root.add_command(self._build_command(command, relaxed=relaxed), command.cli_name)

        return root

    def _build_command(
        self,
        command: Command,
        *,
        relaxed: bool,
        extra_flags: Sequence[ExecutableFlag] = (),
    ) -> InterfacyClickCommand | InterfacyClickGroup:
        group_like = bool(command.subcommands) or command.command_type in ("group", "instance")
        arguments = command.initializer if group_like else command.parameters
        params, bindings, specs, suppressed = self._build_params(
            arguments,
            (*extra_flags, *command.executable_flags),
            relaxed=relaxed or bool(command.subcommands),
        )
        context_settings: dict[str, Any] = {"help_option_names": list(self._config.help_flags)}
        if not group_like:
            native = InterfacyClickCommand(
                name=command.cli_name,
                help=command.description,
                params=params,
                context_settings=context_settings,
            )
            self._attach(native, bindings, specs, suppressed, command)
            return native

        context_settings["allow_interspersed_args"] = False
        native_group = InterfacyClickGroup(
            name=command.cli_name,
            help=command.description,
            params=params,
            context_settings=context_settings,
            invoke_without_command=relaxed or not command.subcommands,
            no_args_is_help=bool(command.subcommands) and not relaxed,
        )
        self._attach(native_group, bindings, specs, suppressed, command)

        if command.subcommands:
            for child in command.subcommands.values():
                native_group.add_command(
                    self._build_command(child, relaxed=relaxed),
                    child.cli_name,
                )

        return native_group

    def _build_params(
        self,
        arguments: Sequence[Argument],
        executable_flags: Sequence[ExecutableFlag],
        *,
        relaxed: bool,
    ) -> tuple[list[click.Parameter], dict[str, str], dict[str, Argument], set[str]]:
        params: list[click.Parameter] = []
        bindings: dict[str, str] = {}
        specs: dict[str, Argument] = {}
        suppressed: set[str] = set()
        used: set[str] = set()
        for argument in arguments:
            param, suppress = self._make_param(argument, used, relaxed=relaxed)
            params.append(param)

            if param.name is not None:
                bindings[param.name] = argument.name

            specs[argument.name] = argument

            if suppress:
                suppressed.add(argument.name)

        params.extend(self._executable_param(flag, used) for flag in executable_flags)

        return params, bindings, specs, suppressed

    def _make_param(
        self,
        argument: Argument,
        used: set[str],
        *,
        relaxed: bool,
    ) -> tuple[click.Parameter, bool]:
        attrs, suppress = self._param_attributes(argument, relaxed=relaxed)
        if argument.kind is ArgumentKind.POSITIONAL:
            maximum = argument.cardinality.maximum_values
            if maximum is None:
                attrs["nargs"] = -1
            elif maximum > 1:
                attrs["nargs"] = maximum

            return InterfacyClickArgument((argument.display_name,), **attrs), suppress

        name = self._sanitize(argument.name, used)
        if argument.value_shape is ValueShape.FLAG:
            behavior = argument.boolean_behavior
            if behavior is None:
                raise ConfigurationError("Boolean flag behavior is required")

            attrs["is_flag"] = True

            return (
                InterfacyBooleanOption(
                    [name, *behavior.positive_flags, *behavior.negative_flags],
                    positive_flags=behavior.positive_flags,
                    negative_flags=behavior.negative_flags,
                    **attrs,
                ),
                suppress,
            )

        declarations = [name, *argument.flags]
        if argument.value_shape is ValueShape.LIST:
            return InterfacyListOption(declarations, **attrs), suppress

        maximum = argument.cardinality.maximum_values
        if maximum is not None and maximum > 1:
            attrs["nargs"] = maximum

        return InterfacyClickOption(declarations, **attrs), suppress

    def _param_attributes(
        self, argument: Argument, *, relaxed: bool
    ) -> tuple[dict[str, Any], bool]:
        is_required = argument.required and argument.cardinality.minimum_values > 0
        attrs: dict[str, Any] = {
            "required": is_required and not relaxed,
            "help": argument.help,
        }
        if argument.metavar and argument.value_shape is not ValueShape.FLAG:
            attrs["metavar"] = argument.metavar
        default = argument.argument_default
        suppress = not default.applies_during_parse
        if default.is_set and not suppress and not is_required:
            attrs["default"] = default.value
        param_type = self._param_type(argument)
        if param_type is not None and argument.value_shape is not ValueShape.FLAG:
            attrs["type"] = param_type

        return attrs, suppress

    @staticmethod
    def _sanitize(name: str, used: set[str]) -> str:
        root = name.replace("-", "_").replace(".", "_").replace(" ", "_")
        if not root.isidentifier():
            root = "param"
        candidate = root
        index = 1
        while candidate in used:
            candidate = f"{root}_{index}"
            index += 1
        used.add(candidate)

        return candidate

    @staticmethod
    def _param_type(argument: Argument) -> click.ParamType | None:
        if argument.choices:
            if argument.parser is not None:
                return ChoiceParamType(argument.choices, argument.parser)
            if all(isinstance(choice, str) for choice in argument.choices):
                return click.Choice([str(choice) for choice in argument.choices])
            return ChoiceParamType(argument.choices, None)

        if argument.parser is not None:
            return ClickFuncParamType(argument.parser, f"parse_{argument.name}")

        return None

    def _executable_param(
        self,
        flag: ExecutableFlag,
        used: set[str],
    ) -> click.Parameter:
        primary = next((item for item in flag.flags if item.startswith("--")), flag.flags[0])
        name = self._sanitize(primary.lstrip("-") or "flag", used)

        def callback(
            context: click.Context,
            parameter: click.Parameter,
            value: bool,
        ) -> None:
            del context, parameter

            if value:
                raise _ExecutableFlagTriggeredError(flag)

        return InterfacyClickOption(
            [name, *flag.flags],
            is_flag=True,
            is_eager=True,
            expose_value=False,
            callback=callback,
            help=flag.help,
        )

    def _attach(
        self,
        native: InterfacyClickCommand | InterfacyClickGroup,
        bindings: dict[str, str],
        specs: dict[str, Argument],
        suppressed: set[str],
        schema: Command | None,
    ) -> None:
        native.interfacy_param_bindings = bindings
        native.interfacy_arg_specs = specs
        native.interfacy_suppress_defaults = suppressed
        native.interfacy_schema = schema
        native.interfacy_aliases = schema.aliases if schema is not None else ()
        native.interfacy_help_layout = self._config.help_layout

    def _parse_root(
        self,
        root: click.Command,
        args: list[str],
        *,
        partial: bool,
        include_defaults: bool,
    ) -> tuple[dict[str, Any], list[str]]:
        context = root.make_context(
            root.name or "main",
            args,
            resilient_parsing=partial,
        )

        if not isinstance(root, (InterfacyClickCommand, InterfacyClickGroup)):
            raise ConfigurationError(f"Unexpected Click root: {type(root)!r}")

        if isinstance(root, InterfacyClickGroup) and root.interfacy_is_root:
            child_info = self._resolve_child_context(context, root, partial=partial)
            if child_info is None:
                return {}, self._remaining(context)

            key, command, child_context = child_info
            namespace = {
                _COMMAND_KEY: key,
                key: self._context_namespace(
                    child_context,
                    command,
                    depth=0,
                    partial=partial,
                    include_defaults=include_defaults,
                ),
            }

            return namespace, self._remaining(child_context)

        namespace = self._context_namespace(
            context,
            root,
            depth=0,
            partial=partial,
            include_defaults=include_defaults,
        )

        return namespace, self._remaining(context)

    def _resolve_child_context(
        self,
        context: click.Context,
        group: InterfacyClickGroup,
        *,
        partial: bool,
    ) -> tuple[str, InterfacyClickCommand | InterfacyClickGroup, click.Context] | None:
        remaining = self._remaining(context)
        if not remaining and partial:
            return None

        name, command, command_args = group.resolve_command(context, remaining)
        if command is None or not isinstance(command, (InterfacyClickCommand, InterfacyClickGroup)):
            return None

        resolved = name or command.name or ""
        child_context = command.make_context(
            resolved,
            command_args,
            parent=context,
            resilient_parsing=partial,
        )
        schema_cmd = command.interfacy_schema
        key = schema_cmd.canonical_name if schema_cmd is not None else resolved

        return key, command, child_context

    def _context_namespace(
        self,
        context: click.Context,
        native: InterfacyClickCommand | InterfacyClickGroup,
        *,
        depth: int,
        partial: bool,
        include_defaults: bool,
    ) -> dict[str, Any]:
        namespace: dict[str, Any] = {}
        for click_name, value in context.params.items():
            schema_name = native.interfacy_param_bindings.get(click_name, click_name)
            source = context.get_parameter_source(click_name)
            if source in (ParameterSource.DEFAULT, ParameterSource.DEFAULT_MAP, None) and (
                not include_defaults or schema_name in native.interfacy_suppress_defaults
            ):
                continue

            namespace[schema_name] = value

        if not isinstance(native, InterfacyClickGroup) or not native.commands:
            return namespace

        child_info = self._resolve_child_context(context, native, partial=partial)
        if child_info is None:
            return namespace

        key, child, child_context = child_info
        destination = f"{_COMMAND_KEY}_{depth}" if depth else _COMMAND_KEY
        namespace[destination] = key
        namespace[key] = self._context_namespace(
            child_context,
            child,
            depth=depth + 1,
            partial=partial,
            include_defaults=include_defaults,
        )

        return namespace

    @staticmethod
    def _remaining(context: click.Context) -> list[str]:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            protected = list(getattr(context, "protected_args", []))
        return [*protected, *context.args]

    def _partial_namespace(self, args: tuple[str, ...]) -> Mapping[str, Any]:
        try:
            root = self._parser_for(ParseRequest(args, "partial", "suppress"))
            namespace, remaining = self._parse_root(
                root,
                list(args),
                partial=True,
                include_defaults=False,
            )
            if remaining:
                return {}

            normalize_schema_values(self._schema, namespace, type_parser=self._config.type_parser)
        except (click.UsageError, _ExecutableFlagTriggeredError, ValueError):
            return {}
        else:
            return namespace


class ClickBackend:
    @property
    def name(self) -> BackendName:
        return "click"

    def compile(
        self,
        schema: ParserSchema,
        help_pipeline: HelpPipeline,
        backend_config: BackendConfig,
    ) -> ClickSession:
        return ClickSession(schema, help_pipeline, backend_config)


__all__ = ["ClickBackend", "ClickSession"]

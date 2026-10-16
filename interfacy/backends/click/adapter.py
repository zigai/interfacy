from __future__ import annotations

import sys
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, NoReturn

import click
from click.core import ParameterSource

from interfacy.backends.base import (
    BackendConfig,
    BackendParseFailure,
    BackendSession,
    ExecutableFlagTriggeredError,
    HelpPipeline,
    NativePresentation,
    ParseOutcome,
    ParseResult,
)
from interfacy.backends.click.commands import (
    InterfacyBooleanOption,
    InterfacyClickArgument,
    InterfacyClickCommand,
    InterfacyClickGroup,
    InterfacyClickOption,
    InterfacyListOption,
)
from interfacy.backends.click.errors import (
    ClickParseContext,
    ClickParseError,
    ClickPresentation,
    argument_label,
)
from interfacy.backends.click.types import ChoiceParamType, ClickFuncParamType
from interfacy.common.resources import ResourceStack
from interfacy.declarations.executable_flags import ExecutableAction, ExecutableFlag
from interfacy.declarations.settings import BackendName
from interfacy.exceptions import ConfigurationError, InterfacyExit, ParseDiagnostic, UsageError
from interfacy.help.diagnostics import diagnostic_message
from interfacy.schema.conversion import ArgumentConversionError, normalize_schema_values
from interfacy.schema.nodes import (
    COMMAND_KEY,
    Argument,
    ArgumentKind,
    Command,
    ParserSchema,
    ValueShape,
)


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

    def parse(self, args: tuple[str, ...]) -> ParseOutcome:
        with ResourceStack() as resources:
            try:
                namespace, supplied, _ = self._parse_root(
                    self._native_parser, list(args), resources, partial=False
                )
                normalize_schema_values(
                    self._schema, namespace, type_parser=self._config.type_parser
                )
                return ParseResult(args, namespace, supplied, resources=resources.pop_all())
            except ExecutableFlagTriggeredError as e:
                return ExecutableAction(e.flag)
            except click.exceptions.Exit as e:
                raise InterfacyExit(e.exit_code) from e
            except click.UsageError as e:
                diagnostic = self._diagnostic(e)
                presentation = ClickPresentation(
                    kind="usage",
                    message=diagnostic_message(diagnostic),
                    diagnostic=diagnostic,
                    command_path=diagnostic.command_path,
                    exit_code=e.exit_code,
                    context=e.ctx,
                )
                partial = self._partial_namespace(args, resources)
                return BackendParseFailure(
                    presentation=presentation,
                    partial_namespace=partial,
                    resources=resources.pop_all(),
                )
            except ValueError as e:
                partial = self._partial_namespace(args, resources)
                diagnostic = (
                    e.diagnostic
                    if isinstance(e, ArgumentConversionError)
                    else ParseDiagnostic(kind="usage")
                )
                return BackendParseFailure(
                    presentation=NativePresentation(
                        kind="usage",
                        message=diagnostic_message(diagnostic),
                        diagnostic=diagnostic,
                        command_path=diagnostic.command_path,
                        exit_code=2,
                    ),
                    partial_namespace=partial,
                    resources=resources.pop_all(),
                )

    def present_error(self, presentation: NativePresentation) -> NoReturn:
        context = presentation.context if isinstance(presentation, ClickPresentation) else None
        if context is None:
            command = self._native_parser
            context = command.context_class(
                command, info_name=self._config.program_name or Path(sys.argv[0]).name
            )
            for segment in presentation.command_path:
                if not isinstance(command, click.Group):
                    break

                child = command.get_command(context, segment)
                if child is None:
                    break

                command = child
                context = command.context_class(command, info_name=segment, parent=context)

        usage = None
        diagnostic = presentation.diagnostic
        if presentation.kind == "usage":
            usage = context.get_usage()

        raise UsageError(
            presentation.message,
            usage=usage,
            diagnostic=diagnostic,
            program=context.command_path,
            exit_code=presentation.exit_code,
        )

    @staticmethod
    def _diagnostic(error: click.UsageError) -> ParseDiagnostic:
        context = error.ctx
        command = context.command if context is not None else None
        path = (
            command.interfacy_help_command_path
            if isinstance(command, (InterfacyClickCommand, InterfacyClickGroup))
            else ()
        )
        parameter = error.param if isinstance(error, click.BadParameter) else None
        label = argument_label(parameter) if parameter is not None else None
        schema_argument = (
            parameter.interfacy_argument
            if isinstance(parameter, (InterfacyClickOption, InterfacyClickArgument))
            else None
        )
        if schema_argument is not None and schema_argument.kind is ArgumentKind.POSITIONAL:
            label = (
                schema_argument.metavar or schema_argument.display_name.replace("_", "-").upper()
            )

        if isinstance(error, ClickParseError):
            diagnostic = error.diagnostic
        elif isinstance(error, click.exceptions.NoArgsIsHelpError):
            diagnostic = ParseDiagnostic(
                kind="missing_subcommand",
                choices=tuple(command.commands) if isinstance(command, click.Group) else (),
            )
        elif isinstance(error, click.NoSuchOption):
            diagnostic = ParseDiagnostic(kind="unknown_option", argument=error.option_name)
        elif isinstance(error, click.MissingParameter):
            diagnostic = ParseDiagnostic(kind="missing_argument", argument=label)
        elif isinstance(error, click.BadParameter):
            parameter_type = parameter.type if parameter is not None else None
            is_choice = isinstance(parameter_type, (click.Choice, ChoiceParamType))
            diagnostic = ParseDiagnostic(
                kind="invalid_choice" if is_choice else "invalid_type",
                argument=label,
                choices=(
                    tuple(str(choice) for choice in parameter_type.choices)
                    if isinstance(parameter_type, (click.Choice, ChoiceParamType))
                    else ()
                ),
            )
        elif isinstance(error, click.BadOptionUsage):
            diagnostic = ParseDiagnostic(kind="usage", argument=error.option_name)
        else:
            diagnostic = ParseDiagnostic(kind="usage")

        expected = diagnostic.expected
        if diagnostic.kind == "invalid_type" and schema_argument is not None:
            expected_types: dict[type[Any] | None, str] = {
                int: "an integer",
                float: "a number",
                str: "text",
            }
            expected = expected_types.get(schema_argument.type, "a valid value")

        return replace(
            diagnostic,
            command_path=path,
            argument=label if parameter is not None else diagnostic.argument,
            expected=expected,
        )

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

        params, bindings, suppressed = self._build_params(
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
        self._attach(root, bindings, suppressed, None)
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
        arguments = command.initializer if group_like else command.arguments
        params, bindings, suppressed = self._build_params(
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
            self._attach(native, bindings, suppressed, command)
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
        self._attach(native_group, bindings, suppressed, command)

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
    ) -> tuple[list[click.Parameter], dict[str, str], set[str]]:
        params: list[click.Parameter] = []
        bindings: dict[str, str] = {}
        suppressed: set[str] = set()
        used: set[str] = set()
        for argument in arguments:
            param, suppress = self._make_param(argument, used, relaxed=relaxed)
            if isinstance(param, (InterfacyClickOption, InterfacyClickArgument)):
                param.interfacy_argument = argument

            params.append(param)

            if param.name is not None:
                bindings[param.name] = argument.name

            if suppress:
                suppressed.add(argument.name)

        params.extend(self._executable_param(flag, used) for flag in executable_flags)

        return params, bindings, suppressed

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
        if argument.value_shape is ValueShape.FLAG:
            is_required = argument.required
        else:
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
                raise ExecutableFlagTriggeredError(flag)

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
        suppressed: set[str],
        schema: Command | None,
    ) -> None:
        native.interfacy_param_bindings = bindings
        native.interfacy_suppress_defaults = suppressed
        native.interfacy_schema = schema
        native.interfacy_aliases = schema.aliases if schema is not None else ()
        native.interfacy_help_layout = self._config.help_layout

    def _parse_root(
        self,
        root: click.Command,
        args: list[str],
        resources: ResourceStack,
        *,
        partial: bool,
    ) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
        """Return the namespace, the part of it given on the command line, and leftovers."""
        context = self._make_context(
            root, self._config.program_name or Path(sys.argv[0]).name, args, resources
        )

        if not isinstance(root, (InterfacyClickCommand, InterfacyClickGroup)):
            raise ConfigurationError(f"Unexpected Click root: {type(root)!r}")

        if isinstance(root, InterfacyClickGroup) and root.interfacy_is_root:
            child_info = self._resolve_child_context(context, root, resources, partial=partial)
            if child_info is None:
                return {}, {}, self._remaining(context)

            key, command, child_context = child_info
            namespace, supplied = self._context_namespace(
                child_context,
                command,
                resources,
                depth=0,
                partial=partial,
            )

            return (
                {COMMAND_KEY: key, key: namespace},
                {COMMAND_KEY: key, key: supplied},
                self._remaining(child_context),
            )

        namespace, supplied = self._context_namespace(
            context, root, resources, depth=0, partial=partial
        )

        return namespace, supplied, self._remaining(context)

    def _resolve_child_context(
        self,
        context: click.Context,
        group: InterfacyClickGroup,
        resources: ResourceStack,
        *,
        partial: bool,
    ) -> tuple[str, InterfacyClickCommand | InterfacyClickGroup, click.Context] | None:
        remaining = self._remaining(context)
        if not remaining:
            if partial or group.invoke_without_command:
                return None

            raise ClickParseError(
                ParseDiagnostic(
                    kind="missing_subcommand", choices=tuple(group.list_commands(context))
                ),
                ctx=context,
            )

        name, command, command_args = group.resolve_command(context, remaining)
        if command is None or not isinstance(command, (InterfacyClickCommand, InterfacyClickGroup)):
            return None

        resolved = name or command.name or ""
        child_context = self._make_context(
            command,
            resolved,
            command_args,
            resources,
            parent=context,
        )
        schema_cmd = command.interfacy_schema
        key = schema_cmd.canonical_name if schema_cmd is not None else resolved

        return key, command, child_context

    def _context_namespace(
        self,
        context: click.Context,
        native: InterfacyClickCommand | InterfacyClickGroup,
        resources: ResourceStack,
        *,
        depth: int,
        partial: bool,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        namespace: dict[str, Any] = {}
        supplied: dict[str, Any] = {}
        for click_name, value in context.params.items():
            schema_name = native.interfacy_param_bindings.get(click_name, click_name)
            source = context.get_parameter_source(click_name)
            if source not in (ParameterSource.DEFAULT, ParameterSource.DEFAULT_MAP, None):
                supplied[schema_name] = value
            elif schema_name in native.interfacy_suppress_defaults:
                continue

            namespace[schema_name] = value

        if not isinstance(native, InterfacyClickGroup) or not native.commands:
            return namespace, supplied

        child_info = self._resolve_child_context(context, native, resources, partial=partial)
        if child_info is None:
            return namespace, supplied

        key, child, child_context = child_info
        destination = f"{COMMAND_KEY}_{depth}" if depth else COMMAND_KEY
        child_namespace, child_supplied = self._context_namespace(
            child_context,
            child,
            resources,
            depth=depth + 1,
            partial=partial,
        )
        namespace[destination] = supplied[destination] = key
        namespace[key] = child_namespace
        supplied[key] = child_supplied

        return namespace, supplied

    @staticmethod
    def _make_context(
        command: click.Command,
        name: str,
        args: list[str],
        resources: ResourceStack,
        *,
        parent: click.Context | None = None,
    ) -> click.Context:
        settings = dict(command.context_settings)
        settings["resilient_parsing"] = False
        context = command.context_class(command, info_name=name, parent=parent, **settings)
        resources.callback(context.close)
        try:
            with context.scope(cleanup=False):
                command.parse_args(context, args)
        except click.UsageError as e:
            if e.ctx is None:
                e.ctx = context

            if not (
                type(e) is click.UsageError
                and isinstance(context, ClickParseContext)
                and context.interfacy_has_extra_args
                and not context.allow_extra_args
                and not context.resilient_parsing
            ):
                raise
        else:
            return context

        raise ClickParseError(ParseDiagnostic(kind="unexpected_argument"), ctx=context)

    @staticmethod
    def _remaining(context: click.Context) -> list[str]:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            protected = list(getattr(context, "protected_args", []))
        return [*protected, *context.args]

    def _partial_namespace(
        self, args: tuple[str, ...], resources: ResourceStack
    ) -> Mapping[str, Any] | None:
        """Return supplied values, or None when relaxing required fields still fails."""
        if self._partial_parser is None:
            self._partial_parser = self._build(self._schema, relaxed=True)

        try:
            _, supplied, remaining = self._parse_root(
                self._partial_parser, list(args), resources, partial=True
            )
            if remaining:
                return None

            normalize_schema_values(self._schema, supplied, type_parser=self._config.type_parser)
        except (click.UsageError, ExecutableFlagTriggeredError, ValueError):
            return None
        else:
            return supplied


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

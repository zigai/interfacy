from __future__ import annotations

import argparse
import re
from collections.abc import Mapping, Sequence
from typing import Any, NoReturn

from interfacy.backends.argparse.actions import BooleanAction, ExecutableFlagAction
from interfacy.backends.argparse.errors import ArgparseParseError
from interfacy.backends.argparse.namespaces import namespace_to_dict, supplied_to_dict
from interfacy.backends.argparse.parser import ArgumentParser, NestedSubParsersAction
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
from interfacy.common.console import warn
from interfacy.declarations.executable_flags import ExecutableAction, ExecutableFlag
from interfacy.declarations.settings import BackendName
from interfacy.exceptions import ConfigurationError, UsageError
from interfacy.schema.conversion import normalize_schema_values
from interfacy.schema.model import (
    COMMAND_KEY,
    SUBCOMMANDS_KEY,
    Argument,
    ArgumentKind,
    Command,
    ParserSchema,
    ValueShape,
    find_command,
)

_SUPPRESSED_DEFAULT = object()


class ArgparseSession(BackendSession[ArgumentParser]):
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
        self._partial_parser: ArgumentParser | None = None
        self._attach_help(self._native_parser, ())
        if config.tab_completion:
            self._install_tab_completion(self._native_parser)

    @property
    def native_parser(self) -> ArgumentParser:
        return self._native_parser

    def parse(self, args: tuple[str, ...]) -> ParseOutcome:
        try:
            namespace, supplied = self._parse(self._native_parser, args)
            namespace = self._normalize(namespace)
        except ExecutableFlagTriggeredError as e:
            return ExecutableAction(e.flag)
        except (ArgparseParseError, argparse.ArgumentError, ValueError) as e:
            return BackendParseFailure(
                presentation=NativePresentation(
                    kind="usage",
                    message=str(e),
                    exit_code=2,
                ),
                partial_namespace=self._best_effort_partial(args),
            )

        self._canonicalize(supplied, self._schema)

        return ParseResult(args=args, namespace=namespace, supplied=supplied)

    def present_error(self, presentation: NativePresentation) -> NoReturn:
        raise UsageError(
            presentation.message,
            usage=self._native_parser.format_usage() if presentation.kind == "usage" else None,
        )

    @staticmethod
    def _parse(
        parser: ArgumentParser,
        args: tuple[str, ...],
        *,
        partial: bool = False,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Return the raw namespace and the part of it given on the command line."""
        parser._interfacy_raise_parse_errors = True
        parser.supplied_dests.clear()
        try:
            if partial:
                parsed, remaining = parser.parse_known_args(list(args))
                if remaining:
                    raise ValueError("unrecognized arguments")
            else:
                parsed = parser.parse_args(list(args))
        finally:
            parser._interfacy_raise_parse_errors = False

        supplied = supplied_to_dict(parsed, parser.supplied_dests, parser.nest_separator)

        return namespace_to_dict(parsed), supplied

    def _attach_help(
        self,
        parser: ArgumentParser,
        command_path: tuple[str, ...],
    ) -> None:
        parser.set_help_pipeline(self._help_pipeline, command_path)
        for action in parser._actions:
            if not isinstance(action, NestedSubParsersAction):
                continue

            seen: set[int] = set()
            for name, child in action.choices.items():
                if id(child) in seen:
                    continue

                seen.add(id(child))
                schema_command = child._schema_command
                canonical = schema_command.canonical_name if schema_command is not None else name
                self._attach_help(child, (*command_path, canonical))

    def _new_parser(self) -> ArgumentParser:
        return ArgumentParser(
            prog=self._config.program_name,
            fromfile_prefix_chars="@" if self._config.allow_args_from_file else None,
            help_layout=self._config.help_layout,
            help_flags=self._config.help_flags,
            sys_exit_enabled=False,
        )

    def _build(
        self,
        schema: ParserSchema,
        *,
        relaxed: bool,
    ) -> ArgumentParser:
        parser = self._new_parser()
        parser.set_schema(schema)
        parser.description = schema.description
        parser.epilog = schema.epilog
        commands = list(schema.commands.values())
        single = commands[0] if len(commands) == 1 else None
        use_root_selection = schema.is_multi_command or (
            single is not None and single.command_type == "group" and not single.is_leaf
        )
        if use_root_selection:
            self._add_executable_flags(parser, schema.executable_flags)
            subparsers = parser.add_subparsers(
                dest=COMMAND_KEY,
                required=not relaxed,
                title="commands",
            )
            for command in commands:
                child = subparsers.add_parser(
                    command.cli_name,
                    aliases=list(command.aliases),
                    description=command.description,
                    help=command.description,
                )
                self._apply_command(
                    child,
                    command,
                    depth=0,
                    relaxed=relaxed,
                )

            self._set_metavar(subparsers)

            return parser

        if single is None:
            raise ConfigurationError("No commands were provided")

        parser.set_schema(None)
        self._apply_command(
            parser,
            single,
            depth=0,
            relaxed=relaxed,
            extra_flags=schema.executable_flags,
        )

        return parser

    def _apply_command(
        self,
        parser: ArgumentParser,
        command: Command,
        *,
        depth: int,
        relaxed: bool,
        extra_flags: Sequence[ExecutableFlag] = (),
    ) -> None:
        parser.set_schema_command(command)
        parser.description = command.description or parser.description
        parser.epilog = command.epilog or parser.epilog
        self._add_executable_flags(parser, (*extra_flags, *command.executable_flags))
        relax_initializer_options = relaxed or bool(command.subcommands)
        for argument in command.initializer:
            argument_relaxed = (
                relax_initializer_options if argument.kind is ArgumentKind.OPTION else relaxed
            )
            self._add_argument(parser, argument, argument_relaxed)

        for argument in command.parameters:
            self._add_argument(parser, argument, relaxed)

        if not command.subcommands:
            return

        subparsers = parser.add_subparsers(
            dest=f"{COMMAND_KEY}_{depth}" if depth else COMMAND_KEY,
            required=not relaxed,
            title="commands",
        )
        for child_command in command.subcommands.values():
            child = subparsers.add_parser(
                child_command.cli_name,
                aliases=list(child_command.aliases),
                description=child_command.description,
                help=child_command.description,
            )
            self._apply_command(
                child,
                child_command,
                depth=depth + 1,
                relaxed=relaxed,
            )

        self._set_metavar(subparsers)

    def _add_argument(
        self,
        parser: ArgumentParser,
        argument: Argument,
        relaxed: bool,
    ) -> None:
        kwargs: dict[str, Any] = {"help": argument.help or ""}
        if argument.metavar and argument.value_shape is not ValueShape.FLAG:
            kwargs["metavar"] = argument.metavar
        nargs = self._native_nargs(argument, relaxed)
        if nargs is not None and argument.value_shape is not ValueShape.FLAG:
            kwargs["nargs"] = nargs

        if argument.value_shape is ValueShape.FLAG:
            behavior = argument.boolean_behavior
            if behavior is None:
                raise ConfigurationError("Boolean flag behavior is required")

            kwargs["action"] = BooleanAction
            kwargs["positive_options"] = behavior.positive_flags
            flags = (*behavior.positive_flags, *behavior.negative_flags)
        else:
            flags = argument.flags
            if argument.parser is not None:
                kwargs["type"] = argument.parser

            if argument.choices:
                kwargs["choices"] = (
                    tuple(argument.parser(choice) for choice in argument.choices)
                    if argument.parser is not None
                    else argument.choices
                )

        if argument.kind is ArgumentKind.OPTION:
            kwargs["dest"] = argument.name
            kwargs["required"] = argument.required and not relaxed
        default = argument.argument_default
        if not default.applies_during_parse:
            kwargs["default"] = _SUPPRESSED_DEFAULT
        elif default.is_set:
            kwargs["default"] = default.value

        parser.add_argument(*flags, **kwargs)

    @staticmethod
    def _native_nargs(argument: Argument, relaxed: bool) -> str | int | None:
        cardinality = argument.cardinality
        if relaxed and argument.required:
            if cardinality.maximum_values is None or cardinality.maximum_values > 1:
                return "*"

            return "?"

        if cardinality.maximum_values is None:
            return "+" if cardinality.minimum_values else "*"

        if cardinality.maximum_values in (0, 1):
            if argument.kind is ArgumentKind.POSITIONAL and cardinality.minimum_values == 0:
                return "?"

            return None

        return cardinality.maximum_values

    @staticmethod
    def _add_executable_flags(
        parser: ArgumentParser,
        flags: Sequence[ExecutableFlag],
    ) -> None:
        for flag in flags:
            primary = next((item for item in flag.flags if item.startswith("--")), flag.flags[0])
            dest = re.sub(r"[^0-9A-Za-z_]+", "_", primary.lstrip("-"))
            parser.add_argument(
                *flag.flags,
                action=ExecutableFlagAction,
                executable_flag=flag,
                dest=f"_interfacy_exec_{dest or 'flag'}",
                default=argparse.SUPPRESS,
                help=flag.help,
            )

    @staticmethod
    def _set_metavar(subparsers: NestedSubParsersAction) -> None:
        names: list[str] = []
        seen: set[int] = set()
        for name, parser in subparsers.choices.items():
            if id(parser) in seen:
                continue

            seen.add(id(parser))
            names.append(name)

        if names:
            subparsers.metavar = "{" + ",".join(names) + "}"

    def _normalize(self, namespace: dict[str, Any]) -> dict[str, Any]:
        self._remove_suppressed(namespace)
        self._canonicalize(namespace, self._schema)
        normalize_schema_values(self._schema, namespace, type_parser=self._config.type_parser)

        return namespace

    def _canonicalize(self, namespace: dict[str, Any], schema: ParserSchema) -> None:
        commands = list(schema.commands.values())
        if len(commands) == 1 and commands[0].command_type != "group":
            self._canonicalize_children(namespace, commands[0])
            return

        selected = namespace.get(COMMAND_KEY)
        if not isinstance(selected, str):
            return

        command = find_command(commands, selected)
        if command is None:
            return

        namespace[COMMAND_KEY] = command.canonical_name
        bucket = namespace.get(selected)
        if isinstance(bucket, dict):
            namespace[command.canonical_name] = bucket
            if selected != command.canonical_name:
                del namespace[selected]

            self._canonicalize_children(bucket, command)

    def _canonicalize_children(
        self,
        namespace: dict[str, Any],
        command: Command,
        depth: int = 0,
    ) -> None:
        if not command.subcommands:
            return

        destination = f"{COMMAND_KEY}_{depth}" if depth else COMMAND_KEY
        selected = namespace.get(destination)
        if not isinstance(selected, str):
            return

        child = find_command(command.subcommands, selected)
        if child is None:
            return

        namespace[destination] = child.canonical_name
        nested = namespace.pop(SUBCOMMANDS_KEY, None)
        child_bucket = namespace.get(selected)
        if not isinstance(child_bucket, dict) and isinstance(nested, dict):
            for name in (selected, child.cli_name, child.canonical_name):
                candidate = nested.get(name)
                if isinstance(candidate, dict):
                    child_bucket = candidate
                    break

        if not isinstance(child_bucket, dict):
            child_bucket = {}

        namespace[child.canonical_name] = child_bucket
        if selected != child.canonical_name:
            namespace.pop(selected, None)

        self._canonicalize_children(child_bucket, child, depth + 1)

    @staticmethod
    def _remove_suppressed(namespace: dict[str, Any]) -> None:
        for key in [key for key, value in namespace.items() if value is _SUPPRESSED_DEFAULT]:
            del namespace[key]

        for value in namespace.values():
            if isinstance(value, dict):
                ArgparseSession._remove_suppressed(value)

    def _best_effort_partial(self, args: tuple[str, ...]) -> Mapping[str, Any]:
        """Return the values given on the command line, or nothing if they do not parse."""
        if self._partial_parser is None:
            self._partial_parser = self._build(self._schema, relaxed=True)

        try:
            _, supplied = self._parse(self._partial_parser, args, partial=True)
            return self._normalize(supplied)
        except (
            ArgparseParseError,
            argparse.ArgumentError,
            ValueError,
            ExecutableFlagTriggeredError,
        ):
            return {}

    @staticmethod
    def _install_tab_completion(parser: ArgumentParser) -> None:
        try:
            import argcomplete
        except ImportError:
            warn(
                "argcomplete not installed. Tab completion not available. "
                "Install with 'pip install argcomplete'"
            )
            return

        argcomplete.autocomplete(parser)


class ArgparseBackend:
    @property
    def name(self) -> BackendName:
        return "argparse"

    def compile(
        self,
        schema: ParserSchema,
        help_pipeline: HelpPipeline,
        backend_config: BackendConfig,
    ) -> ArgparseSession:
        return ArgparseSession(schema, help_pipeline, backend_config)


__all__ = ["ArgparseBackend", "ArgparseSession"]

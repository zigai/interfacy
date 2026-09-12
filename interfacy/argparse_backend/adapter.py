from __future__ import annotations

import argparse
import re
from collections.abc import Mapping, Sequence
from typing import Any, NoReturn

from interfacy.argparse_backend.argument_parser import (
    ArgparseParseError,
    ArgumentParser,
    NestedSubParsersAction,
    namespace_to_dict,
)
from interfacy.console import warn
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
from interfacy.exceptions import ConfigurationError, UsageError
from interfacy.executable_flag import ExecutableAction, ExecutableFlag
from interfacy.schema.schema import (
    Argument,
    ArgumentKind,
    Command,
    ParserSchema,
    ValueShape,
    find_command,
)
from interfacy.schema.value_plan import normalize_schema_values

_SUPPRESSED_DEFAULT = object()
_COMMAND_KEY = "command"


class _ExecutableFlagTriggeredError(Exception):
    def __init__(self, flag: ExecutableFlag) -> None:
        self.flag = flag
        super().__init__(flag.flags[0])


class _ExecutableFlagAction(argparse.Action):
    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        **kwargs: Any,
    ) -> None:
        flag = kwargs.pop("executable_flag")
        if not isinstance(flag, ExecutableFlag):
            raise ConfigurationError("Executable flag action requires ExecutableFlag")

        self.flag = flag
        super().__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: str | None = None,
    ) -> None:
        del parser, namespace, values, option_string
        raise _ExecutableFlagTriggeredError(self.flag)


class _BooleanAction(argparse.Action):
    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        default: Any = None,
        **kwargs: Any,
    ) -> None:
        self.positive = frozenset(kwargs.pop("positive_options"))
        super().__init__(option_strings, dest, nargs=0, default=default, **kwargs)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: str | None = None,
    ) -> None:
        del parser, values
        setattr(namespace, self.dest, option_string in self.positive)


class ArgparseSession(BackendSession[ArgumentParser]):
    def __init__(
        self,
        schema: ParserSchema,
        help_pipeline: HelpPipeline,
        config: BackendConfig,
    ) -> None:
        self._partial_suppressed_parser: ArgumentParser | None = None
        self._schema = schema
        self._help_pipeline = help_pipeline
        self._config = config
        self._native_parser = self._build(schema, relaxed=False, suppress_defaults=False)
        self._partial_parser: ArgumentParser | None = None
        self._attach_help(self._native_parser, ())
        if config.tab_completion:
            self._install_tab_completion(self._native_parser)

        self._suppressed_parser: ArgumentParser | None = None

    @property
    def native_parser(self) -> ArgumentParser:
        return self._native_parser

    def parse(self, request: ParseRequest) -> ParseOutcome:
        parser = self._parser_for(request)
        parser._interfacy_raise_parse_errors = True
        try:
            if request.mode == "partial":
                parsed, remaining = parser.parse_known_args(list(request.args))
            else:
                parsed = parser.parse_args(list(request.args))
                remaining = []
            namespace = self._normalize(namespace_to_dict(parsed))

            return ParseResult(
                args=request.args,
                namespace=namespace,
                remaining_args=tuple(remaining),
            )
        except _ExecutableFlagTriggeredError as e:
            return ExecutableAction(e.flag)
        except (ArgparseParseError, argparse.ArgumentError, ValueError) as e:
            partial = self._best_effort_partial(request.args)
            return BackendParseFailure(
                request=request,
                presentation=NativePresentation(
                    kind="usage",
                    message=str(e),
                    exit_code=2,
                ),
                partial_namespace=partial,
            )
        finally:
            parser._interfacy_raise_parse_errors = False

    def present_error(self, presentation: NativePresentation) -> NoReturn:
        raise UsageError(
            presentation.message,
            usage=self._native_parser.format_usage() if presentation.kind == "usage" else None,
        )

    def _parser_for(self, request: ParseRequest) -> ArgumentParser:
        if request.mode == "partial":
            if request.default_policy == "suppress":
                if self._partial_suppressed_parser is None:
                    self._partial_suppressed_parser = self._build(
                        self._schema,
                        relaxed=True,
                        suppress_defaults=True,
                    )

                return self._partial_suppressed_parser

            if self._partial_parser is None:
                self._partial_parser = self._build(
                    self._schema,
                    relaxed=True,
                    suppress_defaults=False,
                )

            return self._partial_parser

        if request.default_policy == "suppress":
            if self._suppressed_parser is None:
                self._suppressed_parser = self._build(
                    self._schema,
                    relaxed=False,
                    suppress_defaults=True,
                )

            return self._suppressed_parser

        return self._native_parser

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
        )

    def _build(
        self,
        schema: ParserSchema,
        *,
        relaxed: bool,
        suppress_defaults: bool,
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
                dest=_COMMAND_KEY,
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
                    suppress_defaults=suppress_defaults,
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
            suppress_defaults=suppress_defaults,
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
        suppress_defaults: bool,
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
            self._add_argument(parser, argument, argument_relaxed, suppress_defaults)

        for argument in command.parameters:
            self._add_argument(parser, argument, relaxed, suppress_defaults)

        if not command.subcommands:
            return

        subparsers = parser.add_subparsers(
            dest=f"{_COMMAND_KEY}_{depth}" if depth else _COMMAND_KEY,
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
                suppress_defaults=suppress_defaults,
            )

        self._set_metavar(subparsers)

    def _add_argument(
        self,
        parser: ArgumentParser,
        argument: Argument,
        relaxed: bool,
        suppress_defaults: bool,
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

            kwargs["action"] = _BooleanAction
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
        if suppress_defaults or not default.applies_during_parse:
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
                action=_ExecutableFlagAction,
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
        if len(commands) == 1 and not schema.is_multi_command:
            self._canonicalize_children(namespace, commands[0])
            return

        selected = namespace.get(_COMMAND_KEY)
        if not isinstance(selected, str):
            return

        command = find_command(commands, selected)
        if command is None:
            return

        namespace[_COMMAND_KEY] = command.canonical_name
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
    ) -> None:
        if not command.subcommands:
            return

        selected = namespace.get(_COMMAND_KEY)
        if not isinstance(selected, str):
            return

        child = find_command(command.subcommands, selected)
        if child is None:
            return

        namespace[_COMMAND_KEY] = child.canonical_name
        nested = namespace.pop("_subcommands", None)
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

        self._canonicalize_children(child_bucket, child)

    @staticmethod
    def _remove_suppressed(namespace: dict[str, Any]) -> None:
        for key in [key for key, value in namespace.items() if value is _SUPPRESSED_DEFAULT]:
            del namespace[key]

        for value in namespace.values():
            if isinstance(value, dict):
                ArgparseSession._remove_suppressed(value)

    def _best_effort_partial(self, args: tuple[str, ...]) -> Mapping[str, Any]:
        parser = self._parser_for(ParseRequest(args, "partial", "suppress"))
        parser._interfacy_raise_parse_errors = True
        try:
            parsed, remaining = parser.parse_known_args(list(args))
            if remaining:
                return {}

            return self._normalize(namespace_to_dict(parsed))
        except (
            ArgparseParseError,
            argparse.ArgumentError,
            ValueError,
            _ExecutableFlagTriggeredError,
        ):
            return {}
        finally:
            parser._interfacy_raise_parse_errors = False

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

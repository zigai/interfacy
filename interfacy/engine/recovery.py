from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from interfacy.backends.base import BackendParseFailure, BackendSession, NativePresentation
from interfacy.declarations.settings import BackendName
from interfacy.engine.parsing import InvocationState, bucket_for_command_path
from interfacy.engine.plugins import PluginManager
from interfacy.exceptions import ConfigurationError
from interfacy.plugins import (
    AbortRecovery,
    ArgumentDescriptor,
    ArgumentRef,
    ParseFailure,
    ParseFailureContext,
    ParseFailureKind,
    ProvideArgumentValues,
    SchemaDescriptor,
)
from interfacy.schema.model import COMMAND_KEY, Command, ParserSchema, find_command


def usage_presentation(message: str, exit_code: int = 2) -> NativePresentation:
    """Return a usage-error presentation for ``message``."""
    return NativePresentation(kind="usage", message=message, exit_code=exit_code)


def recover_parse_failure(
    session: BackendSession[object],
    schema: ParserSchema,
    state: InvocationState,
    initial: BackendParseFailure,
    *,
    backend: BackendName,
    metadata: Mapping[str, Any],
    plugin_manager: PluginManager,
    max_attempts: int,
) -> dict[str, Any]:
    """
    Let recovery plugins complete a partial namespace after a backend parse failure.

    Returns the recovered namespace once no required argument is missing. Otherwise the
    backend presents the original failure, which does not return.
    """
    failure = initial
    namespace = dict(failure.partial_namespace)
    while state.recovery_attempts < max_attempts:
        state.recovery_attempts += 1
        descriptor = parse_failure(schema, namespace, failure.presentation.message)
        action = plugin_manager.recover(
            ParseFailureContext(
                backend=backend,
                metadata=metadata,
                schema=SchemaDescriptor.from_schema(schema),
                args=state.args,
                namespace=namespace,
            ),
            descriptor,
        )
        if action is None:
            break

        if isinstance(action, AbortRecovery):
            message = action.message or failure.presentation.message
            session.present_error(usage_presentation(message, action.exit_code))

        apply_recovery_action(schema, namespace, descriptor, action)

        if not missing_required(schema, namespace):
            return namespace

    return session.present_error(failure.presentation)


def apply_recovery_action(
    schema: ParserSchema,
    namespace: dict[str, Any],
    failure: ParseFailure,
    action: ProvideArgumentValues,
) -> None:
    """Write recovered argument values and subcommand selections into ``namespace``."""
    missing = set(failure.missing_arguments)
    for ref, value in action.values.items():
        if ref not in missing:
            raise ConfigurationError(
                f"Recovery provided value for non-missing argument '{ref.name}'"
            )

        bucket = bucket_for_command_path(
            namespace,
            ref.command_path,
            create=True,
        )
        if bucket is not None:
            bucket[ref.name] = value

    for path, command_name in action.subcommands.items():
        subcommands = subcommands_at_path(schema, path)
        selected = find_command(subcommands, command_name)
        if selected is None:
            raise ConfigurationError(f"Recovery selected invalid subcommand '{command_name}'")

        bucket = bucket_for_command_path(
            namespace,
            path,
            create=True,
        )
        if bucket is not None:
            bucket[COMMAND_KEY] = selected.canonical_name
            bucket.setdefault(selected.canonical_name, {})


def parse_failure(
    schema: ParserSchema,
    namespace: dict[str, Any],
    message: str,
) -> ParseFailure:
    """Describe a recoverable parse failure for the partial ``namespace``."""
    missing = tuple(missing_required(schema, namespace))
    kind = ParseFailureKind.MISSING_ARGUMENTS if missing else ParseFailureKind.MISSING_SUBCOMMAND

    return ParseFailure(
        kind=kind,
        message=message,
        command_path=missing[0].command_path if missing else (),
        command_depth=len(missing[0].command_path) if missing else 0,
        missing_arguments=missing,
        available_subcommands=tuple(sorted(available_subcommands(schema, ()))),
    )


def missing_required(
    schema: ParserSchema,
    namespace: dict[str, Any],
) -> list[ArgumentRef]:
    """Return references to required top-level command arguments absent from ``namespace``."""
    missing: list[ArgumentRef] = []
    single = len(schema.commands) == 1 and not schema.is_multi_command
    for command in schema.commands.values():
        path = () if single else (command.canonical_name,)
        bucket = namespace if single else namespace.get(command.canonical_name, {})
        if not isinstance(bucket, dict):
            bucket = {}
        missing.extend(
            ArgumentRef(path, argument.name, ArgumentDescriptor.from_argument(path, argument))
            for argument in (*command.initializer, *command.parameters)
            if argument.required and argument.name not in bucket
        )

    return missing


def subcommands_at_path(
    schema: ParserSchema,
    path: tuple[str, ...],
) -> dict[str, Command]:
    """Return the subcommands selectable at ``path``, or an empty mapping if it is unknown."""
    commands = schema.commands
    if not path:
        if len(commands) == 1 and not schema.is_multi_command:
            root = next(iter(commands.values()))
            if root.command_type != "group" and root.subcommands:
                return root.subcommands

        return commands

    for segment in path:
        current = find_command(commands, segment)
        if current is None:
            return {}

        commands = current.subcommands or {}

    return commands


def available_subcommands(
    schema: ParserSchema,
    path: tuple[str, ...],
) -> set[str]:
    """Return every name and alias selectable at ``path``."""
    return {
        name
        for item in subcommands_at_path(schema, path).values()
        for name in (item.canonical_name, item.cli_name, *item.aliases)
    }


__all__ = [
    "apply_recovery_action",
    "available_subcommands",
    "missing_required",
    "parse_failure",
    "recover_parse_failure",
    "subcommands_at_path",
    "usage_presentation",
]

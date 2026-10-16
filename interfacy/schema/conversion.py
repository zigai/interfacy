from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from strto import StrToTypeParser

    from interfacy.schema.nodes import Argument, Command, ParserSchema

from interfacy.exceptions import ParseDiagnostic
from interfacy.schema.nodes import ArgumentKind
from interfacy.schema.values import RepeatedValue, as_sequence, plan_requires_post_conversion


class ArgumentConversionError(ValueError):
    def __init__(self, diagnostic: ParseDiagnostic) -> None:
        self.diagnostic = diagnostic
        super().__init__(f"Invalid value for {diagnostic.argument!r}")


def _normalize_argument_value(
    argument: Argument,
    bucket: dict[str, Any],
    *,
    type_parser: StrToTypeParser | None,
    command_path: tuple[str, ...],
) -> None:
    if argument.name not in bucket or bucket[argument.name] is None:
        return

    value_plan = argument.value_plan
    if value_plan is None:
        return

    if not plan_requires_post_conversion(value_plan, required=argument.required):
        if isinstance(value_plan, RepeatedValue):
            bucket[argument.name] = list(as_sequence(bucket[argument.name]))

        return

    try:
        bucket[argument.name] = value_plan.convert(bucket[argument.name], type_parser=type_parser)
    except (TypeError, ValueError, KeyError):
        pass
    else:
        return

    label = argument.metavar or argument.display_name.replace("_", "-").upper()
    if argument.kind is ArgumentKind.OPTION:
        label = next((flag for flag in argument.flags if flag.startswith("--")), argument.flags[0])

    raise ArgumentConversionError(
        ParseDiagnostic(
            kind="invalid_choice" if argument.choices is not None else "invalid_type",
            command_path=command_path,
            argument=label,
            choices=tuple(str(choice) for choice in argument.choices or ()),
        )
    )


def normalize_argument_values(
    command: Command,
    bucket: dict[str, Any],
    *,
    type_parser: StrToTypeParser | None,
    command_path: tuple[str, ...],
) -> None:
    for argument in (*command.initializer, *command.arguments):
        _normalize_argument_value(
            argument, bucket, type_parser=type_parser, command_path=command_path
        )

    if not command.subcommands:
        return

    for sub_cmd in command.subcommands.values():
        sub_bucket = bucket.get(sub_cmd.canonical_name)
        if not isinstance(sub_bucket, dict):
            sub_bucket = bucket.get(sub_cmd.cli_name)

        if isinstance(sub_bucket, dict):
            normalize_argument_values(
                sub_cmd,
                sub_bucket,
                type_parser=type_parser,
                command_path=(*command_path, sub_cmd.canonical_name),
            )


def normalize_schema_values(
    schema: ParserSchema, namespace: dict[str, Any], *, type_parser: StrToTypeParser | None
) -> None:
    """Normalize present command buckets after a backend has canonicalized their names."""
    if len(schema.commands) == 1:
        command = next(iter(schema.commands.values()))
        bucket = (
            namespace.get(command.canonical_name) if command.command_type == "group" else namespace
        )
        if isinstance(bucket, dict):
            normalize_argument_values(
                command,
                bucket,
                type_parser=type_parser,
                command_path=(command.canonical_name,) if command.command_type == "group" else (),
            )

        return

    for command in schema.commands.values():
        bucket = namespace.get(command.canonical_name)
        if isinstance(bucket, dict):
            normalize_argument_values(
                command,
                bucket,
                type_parser=type_parser,
                command_path=(command.canonical_name,),
            )


__all__ = [
    "ArgumentConversionError",
    "normalize_argument_values",
    "normalize_schema_values",
]

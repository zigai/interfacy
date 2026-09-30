from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from interfacy.schema.model import ParserSchema

from interfacy.schema.values import RepeatedValue, as_sequence, plan_requires_post_conversion


def _normalize_argument_value(
    argument: Any,
    bucket: dict[str, Any],
    *,
    type_parser: Any,
) -> None:
    if argument.name not in bucket or bucket[argument.name] is None:
        return

    value_plan = argument.value_plan
    if not plan_requires_post_conversion(value_plan, required=argument.required):
        if isinstance(value_plan, RepeatedValue):
            bucket[argument.name] = list(as_sequence(bucket[argument.name]))

        return

    bucket[argument.name] = value_plan.convert(bucket[argument.name], type_parser=type_parser)


def normalize_argument_values(command: Any, bucket: dict[str, Any], *, type_parser: Any) -> None:
    for argument in (*command.initializer, *command.parameters):
        _normalize_argument_value(argument, bucket, type_parser=type_parser)

    if not command.subcommands:
        return

    for sub_cmd in command.subcommands.values():
        sub_bucket = bucket.get(sub_cmd.canonical_name)
        if not isinstance(sub_bucket, dict):
            sub_bucket = bucket.get(sub_cmd.cli_name)

        if isinstance(sub_bucket, dict):
            normalize_argument_values(sub_cmd, sub_bucket, type_parser=type_parser)


def normalize_schema_values(
    schema: ParserSchema, namespace: dict[str, Any], *, type_parser: Any
) -> None:
    """Normalize present command buckets after a backend has canonicalized their names."""
    if len(schema.commands) == 1:
        command = next(iter(schema.commands.values()))
        bucket = (
            namespace.get(command.canonical_name) if command.command_type == "group" else namespace
        )
        if isinstance(bucket, dict):
            normalize_argument_values(command, bucket, type_parser=type_parser)

        return

    for command in schema.commands.values():
        bucket = namespace.get(command.canonical_name)
        if isinstance(bucket, dict):
            normalize_argument_values(command, bucket, type_parser=type_parser)


__all__ = [
    "normalize_argument_values",
    "normalize_schema_values",
]

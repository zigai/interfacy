from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class TokenConsumption:
    """How many CLI values are needed to build one Python value."""

    minimum_values: int
    maximum_values: int | None
    group_size: int

    @property
    def is_fixed(self) -> bool:
        return self.maximum_values == self.minimum_values


class ArgumentValue(Protocol):
    """Internal conversion plan for an argument value."""

    def token_consumption(self, *, required: bool) -> TokenConsumption: ...

    def convert(self, raw: Any, *, type_parser: Any) -> Any: ...


@dataclass(frozen=True)
class UntypedValue:
    def token_consumption(self, *, required: bool) -> TokenConsumption:
        minimum = 1 if required else 0
        return TokenConsumption(minimum, 1, 1)

    def convert(self, raw: Any, *, type_parser: Any) -> Any:  # noqa: ARG002
        return raw


@dataclass(frozen=True)
class FlagValue:
    def token_consumption(self, *, required: bool) -> TokenConsumption:  # noqa: ARG002
        return TokenConsumption(0, 0, 0)

    def convert(self, raw: Any, *, type_parser: Any) -> Any:  # noqa: ARG002
        return raw


@dataclass(frozen=True)
class ScalarValue:
    annotation: Any

    def token_consumption(self, *, required: bool) -> TokenConsumption:
        minimum = 1 if required else 0
        return TokenConsumption(minimum, 1, 1)

    def convert(self, raw: Any, *, type_parser: Any) -> Any:
        if raw is None:
            return None
        if self.annotation is str:
            return raw

        return type_parser.parse(raw, self.annotation)


@dataclass(frozen=True)
class RepeatedValue:
    item: ArgumentValue

    def token_consumption(self, *, required: bool) -> TokenConsumption:
        item_consumption = self.item.token_consumption(required=True)
        minimum = item_consumption.group_size if required else 0
        return TokenConsumption(minimum, None, item_consumption.group_size)

    def convert(self, raw: Any, *, type_parser: Any) -> Any:
        if raw is None:
            return None

        values = _as_sequence(raw)
        item_consumption = self.item.token_consumption(required=True)
        group_size = item_consumption.group_size
        if group_size <= 1:
            return [self.item.convert(item, type_parser=type_parser) for item in values]
        if len(values) % group_size != 0:
            raise ValueError(
                f"expected values in groups of {group_size}, got {len(values)} value(s)"
            )

        return [
            self.item.convert(values[index : index + group_size], type_parser=type_parser)
            for index in range(0, len(values), group_size)
        ]


@dataclass(frozen=True)
class FixedTupleValue:
    items: tuple[ArgumentValue, ...]

    def token_consumption(self, *, required: bool) -> TokenConsumption:
        total = sum(item.token_consumption(required=True).group_size for item in self.items)
        minimum = total if required else 0
        return TokenConsumption(minimum, total, total)

    def convert(self, raw: Any, *, type_parser: Any) -> tuple[Any, ...]:
        values = _as_sequence(raw)
        expected = self.token_consumption(required=True).group_size
        if len(values) != expected:
            raise ValueError(f"expected {expected} value(s), got {len(values)}")

        converted: list[Any] = []
        offset = 0
        for item in self.items:
            group_size = item.token_consumption(required=True).group_size
            chunk = values[offset : offset + group_size]
            value: Any = chunk[0] if group_size == 1 else chunk
            converted.append(item.convert(value, type_parser=type_parser))

            offset += group_size

        return tuple(converted)


@dataclass(frozen=True)
class ObjectFieldValue:
    name: str
    value: ArgumentValue


@dataclass(frozen=True)
class ObjectValue:
    model_type: type[Any]
    fields: tuple[ObjectFieldValue, ...]

    def token_consumption(self, *, required: bool) -> TokenConsumption:
        total = sum(
            field.value.token_consumption(required=True).group_size for field in self.fields
        )
        minimum = total if required else 0
        return TokenConsumption(minimum, total, total)

    def convert(self, raw: Any, *, type_parser: Any) -> Any:
        values = _as_sequence(raw)
        expected = self.token_consumption(required=True).group_size
        if len(values) != expected:
            raise ValueError(f"expected {expected} value(s), got {len(values)}")

        kwargs: dict[str, Any] = {}
        offset = 0
        for field in self.fields:
            group_size = field.value.token_consumption(required=True).group_size
            chunk = values[offset : offset + group_size]
            value: Any = chunk[0] if group_size == 1 else chunk
            kwargs[field.name] = field.value.convert(value, type_parser=type_parser)
            offset += group_size

        return self.model_type(**kwargs)


def _as_sequence(raw: Any) -> Sequence[Any]:
    if isinstance(raw, (tuple, list)):
        return raw

    return (raw,)


def plan_requires_post_conversion(value_plan: ArgumentValue | None, *, required: bool) -> bool:
    if value_plan is None:
        return False

    consumption = value_plan.token_consumption(required=required)

    return consumption.group_size > 1


def convert_with_value_plan(
    value_plan: ArgumentValue | None,
    raw: Any,
    *,
    type_parser: Any,
) -> Any:
    if value_plan is None:
        return raw

    return value_plan.convert(raw, type_parser=type_parser)


def normalize_argument_values(command: Any, bucket: dict[str, Any], *, type_parser: Any) -> None:
    for argument in (*command.initializer, *command.parameters):
        if argument.name not in bucket:
            continue

        if not plan_requires_post_conversion(argument.value_plan, required=argument.required):
            continue
        bucket[argument.name] = convert_with_value_plan(
            argument.value_plan,
            bucket[argument.name],
            type_parser=type_parser,
        )

    if not command.subcommands:
        return

    for sub_cmd in command.subcommands.values():
        sub_bucket = bucket.get(sub_cmd.cli_name)
        if isinstance(sub_bucket, dict):
            normalize_argument_values(sub_cmd, sub_bucket, type_parser=type_parser)

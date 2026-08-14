from dataclasses import dataclass

import pytest
from objinspect import Class, Function

from interfacy.exceptions import ReservedFlagError
from interfacy.schema.builder import ParserSchemaBuilder
from interfacy.schema.schema import ArgumentKind, ValueShape
from interfacy.schema.value_plan import FixedTupleValue, ObjectValue, RepeatedValue
from tests.fixtures.models import Color
from tests.unit.schema.conftest import SchemaSource, StubTypeParser


def reserved(help: int) -> None:
    return None


class NeedsCommandKey:
    def __init__(self, command: int) -> None:
        self.command = command

    def run(self) -> None: ...


def typed_optional_union(values: list[int] | None) -> list[int] | None:
    return values


def optional_list(values: list[int] | None = None) -> list[int] | None:
    return values


def color_list(values: list[Color]): ...


@dataclass
class User:
    name: str
    age: int


def list_of_tuples(values: list[tuple[int, str]]) -> list[tuple[int, str]]:
    return values


def tuple_of_users(pair: tuple[User, User]) -> tuple[User, User]:
    return pair


def positional_value(value: int) -> int:
    return value


BOOL_TRISTATE_DEFAULT = None


def bool_tristate(flag: bool = BOOL_TRISTATE_DEFAULT) -> bool | None:
    return flag


def bool_positional(flag: bool) -> bool:
    return flag


def untyped(value):
    return value


def test_reserved_flag_name_raises(schema_source: SchemaSource) -> None:
    """Verify that reserved flag names raise a ReservedFlagError."""
    builder = ParserSchemaBuilder(schema_source.schema_context())
    param = Function(reserved).params[0]
    with pytest.raises(ReservedFlagError) as exc:
        builder._argument_from_parameter(param, [*schema_source.RESERVED_FLAGS])

    assert "help" in str(exc.value)


def test_command_key_collision_raises(schema_source: SchemaSource) -> None:
    """Verify that command key collisions raise a ReservedFlagError."""
    schema_source.COMMAND_KEY = "command"
    builder = ParserSchemaBuilder(schema_source.schema_context())

    with pytest.raises(ReservedFlagError):
        builder._class_command(
            Class(NeedsCommandKey),
            canonical_name="needs-command",
        )


def test_optional_union_list_defaults_are_isolated(schema_source: SchemaSource) -> None:
    """Verify that default values for mutable types (lists) are isolated across arguments."""
    builder = ParserSchemaBuilder(schema_source.schema_context())
    param = Function(typed_optional_union).params[0]
    taken = [*schema_source.RESERVED_FLAGS]

    arg1 = builder._argument_from_parameter(param, taken[:])[0]
    arg2 = builder._argument_from_parameter(param, taken[:])[0]

    assert arg1.value_shape is ValueShape.LIST
    assert arg1.argument_default.value == []
    assert arg2.argument_default.value == []
    assert arg1.argument_default.value is not arg2.argument_default.value
    assert arg1.required is False


def test_pipe_optional_list_keeps_nargs(schema_source: SchemaSource) -> None:
    """Verify that piped optional list arguments retain their variable-length nargs setting."""
    builder = ParserSchemaBuilder(schema_source.schema_context())
    param = Function(optional_list).params[0]
    argument = builder._argument_from_parameter(
        param,
        [*schema_source.RESERVED_FLAGS],
        pipe_param_names={"values"},
    )[0]

    assert argument.accepts_stdin is True
    assert argument.pipe_required is False
    assert argument.cardinality.minimum_values == 0
    assert argument.cardinality.maximum_values is None
    assert argument.required is False


def test_pipe_required_relaxes_required_positional(schema_source: SchemaSource) -> None:
    """Verify that required positional arguments become optional when configured for pipe input."""
    builder = ParserSchemaBuilder(schema_source.schema_context())
    param = Function(positional_value).params[0]
    argument = builder._argument_from_parameter(
        param,
        [*schema_source.RESERVED_FLAGS],
        pipe_param_names={"value"},
    )[0]

    assert argument.accepts_stdin is True
    assert argument.pipe_required is True
    assert argument.required is False
    assert argument.cardinality.minimum_values == 0
    assert argument.cardinality.maximum_values == 1


def test_boolean_preserves_none_default(schema_source: SchemaSource) -> None:
    """Verify that boolean arguments preserve explicit None defaults (tristate behavior)."""
    builder = ParserSchemaBuilder(schema_source.schema_context())
    param = Function(bool_tristate).params[0]
    argument = builder._argument_from_parameter(param, [*schema_source.RESERVED_FLAGS])[0]

    assert argument.boolean_behavior is not None
    assert argument.boolean_behavior.default is None
    assert argument.argument_default.value is None


def test_bool_positional_still_option(schema_source: SchemaSource) -> None:
    """Verify that boolean positional arguments are treated as options (flags)."""
    builder = ParserSchemaBuilder(schema_source.schema_context())
    param = Function(bool_positional).params[0]
    argument = builder._argument_from_parameter(param, [*schema_source.RESERVED_FLAGS])[0]

    assert argument.kind is ArgumentKind.OPTION
    assert argument.value_shape is ValueShape.FLAG


def test_untyped_parameter_has_no_parser(schema_source: SchemaSource) -> None:
    """Verify that untyped parameters result in arguments with no assigned parser."""
    builder = ParserSchemaBuilder(schema_source.schema_context())
    param = Function(untyped).params[0]
    argument = builder._argument_from_parameter(param, [*schema_source.RESERVED_FLAGS])[0]

    assert argument.parser is None
    assert argument.choices is None


def test_nested_enum_list_requests_type_parser() -> None:
    """Verify that nested Enum lists properly request a type parser for the Enum type."""
    type_parser = StubTypeParser()
    parser = SchemaSource(type_parser=type_parser)
    builder = ParserSchemaBuilder(parser.schema_context())
    param = Function(color_list).params[0]

    parse_color = lambda raw: Color[raw]  # noqa
    type_parser.register(Color, parse_color)

    argument = builder._argument_from_parameter(
        param,
        [*parser.RESERVED_FLAGS],
    )[0]

    assert argument.value_shape is ValueShape.LIST
    assert argument.parser is parse_color
    assert type_parser.requests == [Color]


def test_list_of_fixed_tuples_builds_repeated_value_plan(schema_source: SchemaSource) -> None:
    """Verify nested repeated tuple values collect raw tokens for later conversion."""
    builder = ParserSchemaBuilder(schema_source.schema_context())
    param = Function(list_of_tuples).params[0]

    argument = builder._argument_from_parameter(param, [*schema_source.RESERVED_FLAGS])[0]

    assert argument.value_shape is ValueShape.LIST
    assert argument.parser is None
    assert isinstance(argument.value_plan, RepeatedValue)
    assert isinstance(argument.value_plan.item, FixedTupleValue)
    assert argument.value_plan.token_consumption(required=True).group_size == 2


def test_tuple_of_dataclasses_builds_object_value_plan(schema_source: SchemaSource) -> None:
    """Verify fixed tuples can plan fixed-size model values."""
    builder = ParserSchemaBuilder(schema_source.schema_context())
    param = Function(tuple_of_users).params[0]

    argument = builder._argument_from_parameter(param, [*schema_source.RESERVED_FLAGS])[0]

    assert argument.value_shape is ValueShape.TUPLE
    assert argument.parser is None
    assert argument.cardinality.minimum_values == 4
    assert argument.cardinality.maximum_values == 4
    assert argument.cardinality.group_size == 4
    assert isinstance(argument.value_plan, FixedTupleValue)
    assert all(isinstance(item, ObjectValue) for item in argument.value_plan.items)

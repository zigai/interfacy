import pytest
from objinspect import Class, Function

from interfacy.exceptions import ReservedFlagError
from interfacy.schema.builder import ParserSchemaBuilder
from interfacy.schema.schema import ArgumentKind, ValueShape
from tests.conftest import Color
from tests.schema.conftest import FakeParser, StubTypeParser


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


def positional_value(value: int) -> int:
    return value


def bool_tristate(flag: bool = None) -> bool | None:
    return flag


def bool_positional(flag: bool) -> bool:
    return flag


def untyped(value):
    return value


def test_reserved_flag_name_raises(builder_parser: FakeParser) -> None:
    """Verify that reserved flag names raise a ReservedFlagError."""
    builder = ParserSchemaBuilder(builder_parser)
    param = Function(reserved).params[0]
    with pytest.raises(ReservedFlagError) as exc:
        builder._argument_from_parameter(param, [*builder_parser.RESERVED_FLAGS])
    assert "help" in str(exc.value)


def test_command_key_collision_raises(builder_parser: FakeParser) -> None:
    """Verify that command key collisions raise a ReservedFlagError."""
    builder_parser.COMMAND_KEY = "command"
    builder = ParserSchemaBuilder(builder_parser)

    with pytest.raises(ReservedFlagError):
        builder._class_command(
            Class(NeedsCommandKey),
            canonical_name="needs-command",
        )


def test_optional_union_list_defaults_are_isolated(builder_parser: FakeParser) -> None:
    """Verify that default values for mutable types (lists) are isolated across arguments."""
    builder = ParserSchemaBuilder(builder_parser)
    param = Function(typed_optional_union).params[0]
    taken = [*builder_parser.RESERVED_FLAGS]

    arg1 = builder._argument_from_parameter(param, taken[:])[0]
    arg2 = builder._argument_from_parameter(param, taken[:])[0]

    assert arg1.value_shape is ValueShape.LIST
    assert arg1.default == []
    assert arg2.default == []
    assert arg1.default is not arg2.default
    assert arg1.required is False


def test_pipe_optional_list_keeps_nargs(builder_parser: FakeParser) -> None:
    """Verify that piped optional list arguments retain their variable-length nargs setting."""
    builder = ParserSchemaBuilder(builder_parser)
    param = Function(optional_list).params[0]
    argument = builder._argument_from_parameter(
        param,
        [*builder_parser.RESERVED_FLAGS],
        pipe_param_names={"values"},
    )[0]

    assert argument.accepts_stdin is True
    assert argument.pipe_required is False
    assert argument.nargs == "*"
    assert argument.required is False


def test_pipe_required_relaxes_required_positional(builder_parser: FakeParser) -> None:
    """Verify that required positional arguments become optional when configured for pipe input."""
    builder = ParserSchemaBuilder(builder_parser)
    param = Function(positional_value).params[0]
    argument = builder._argument_from_parameter(
        param,
        [*builder_parser.RESERVED_FLAGS],
        pipe_param_names={"value"},
    )[0]

    assert argument.accepts_stdin is True
    assert argument.pipe_required is True
    assert argument.required is False
    assert argument.nargs == "?"


def test_boolean_preserves_none_default(builder_parser: FakeParser) -> None:
    """Verify that boolean arguments preserve explicit None defaults (tristate behavior)."""
    builder = ParserSchemaBuilder(builder_parser)
    param = Function(bool_tristate).params[0]
    argument = builder._argument_from_parameter(param, [*builder_parser.RESERVED_FLAGS])[0]

    assert argument.boolean_behavior is not None
    assert argument.boolean_behavior.default is None
    assert argument.default is None


def test_bool_positional_still_option(builder_parser: FakeParser) -> None:
    """Verify that boolean positional arguments are treated as options (flags)."""
    builder = ParserSchemaBuilder(builder_parser)
    param = Function(bool_positional).params[0]
    argument = builder._argument_from_parameter(param, [*builder_parser.RESERVED_FLAGS])[0]

    assert argument.kind is ArgumentKind.OPTION
    assert argument.value_shape is ValueShape.FLAG


def test_untyped_parameter_has_no_parser(builder_parser: FakeParser) -> None:
    """Verify that untyped parameters result in arguments with no assigned parser."""
    builder = ParserSchemaBuilder(builder_parser)
    param = Function(untyped).params[0]
    argument = builder._argument_from_parameter(param, [*builder_parser.RESERVED_FLAGS])[0]

    assert argument.parser is None
    assert argument.choices is None


def test_nested_enum_list_requests_type_parser() -> None:
    """Verify that nested Enum lists properly request a type parser for the Enum type."""
    type_parser = StubTypeParser()
    parser = FakeParser(type_parser=type_parser)
    builder = ParserSchemaBuilder(parser)
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

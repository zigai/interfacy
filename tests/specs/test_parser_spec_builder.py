import inspect

import pytest

from interfacy.argparse_backend import Argparser
from interfacy.naming import DefaultFlagStrategy
from interfacy.schema.schema import ArgumentKind, ValueShape
from tests.conftest import (
    Color,
    Math,
    function_bool_default_true,
    function_bool_short_flag,
    function_enum_arg,
    function_list_int,
    function_list_with_default,
    pow,
)


def doc_summary(obj) -> str | None:
    doc = inspect.getdoc(obj)
    if not doc:
        return None
    return doc.splitlines()[0]


@pytest.fixture
def parser():
    return Argparser(
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        sys_exit_enabled=False,
        help_layout=None,
    )


def test_function_command_includes_positional_and_option(parser: Argparser):
    parser.add_command(pow)

    schema = parser.build_parser_schema()
    assert schema.command_key == "command"
    assert schema.pipe_targets is None
    assert not schema.is_multi_command

    command = schema.commands["pow"]
    assert command.canonical_name == "pow"
    assert command.cli_name == "pow"
    assert command.raw_description == doc_summary(pow)

    base_arg = command.parameters[0]
    assert base_arg.display_name == "base"
    assert base_arg.flags == ("base",)
    assert base_arg.kind is ArgumentKind.POSITIONAL
    assert base_arg.value_shape is ValueShape.SINGLE
    assert base_arg.required is True
    assert base_arg.default is None
    assert base_arg.type is int
    assert callable(base_arg.parser)

    exponent_arg = command.parameters[1]
    assert exponent_arg.display_name == "exponent"
    assert exponent_arg.flags == ("-e", "--exponent")
    assert exponent_arg.kind is ArgumentKind.OPTION
    assert exponent_arg.value_shape is ValueShape.SINGLE
    assert exponent_arg.required is False
    assert exponent_arg.default == 2
    assert exponent_arg.metavar == "\b"
    assert exponent_arg.type is int
    assert callable(exponent_arg.parser)


def test_class_command_exposes_initializer_and_subcommands(parser: Argparser):
    parser.add_command(Math)

    schema = parser.build_parser_schema()
    assert schema.is_multi_command is False

    command = schema.commands["math"]
    assert command.canonical_name == "math"
    assert command.cli_name == "math"
    assert command.raw_description == doc_summary(Math)
    assert command.initializer, "expected class initializer parameters"

    rounding_arg = command.initializer[0]
    assert rounding_arg.display_name == "rounding"
    assert rounding_arg.flags == ("-r", "--rounding")
    assert rounding_arg.required is False
    assert rounding_arg.default == 6
    assert rounding_arg.type is int
    assert rounding_arg.metavar == "\b"

    assert command.subcommands is not None
    assert set(command.subcommands) == {"add", "pow", "subtract"}

    pow_command = command.subcommands["pow"]
    assert pow_command.cli_name == "pow"
    assert [arg.display_name for arg in pow_command.parameters] == ["base", "exponent"]


def test_boolean_argument_annotated_with_boolean_behavior(parser: Argparser):
    parser.add_command(function_bool_default_true)

    schema = parser.build_parser_schema()
    command = schema.commands["function-bool-default-true"]
    argument = command.parameters[0]

    assert argument.flags == ("--value",)
    assert argument.value_shape is ValueShape.FLAG
    assert argument.boolean_behavior is not None
    assert argument.boolean_behavior.supports_negative is True
    assert argument.boolean_behavior.negative_form == "--no-value"
    assert argument.boolean_behavior.default is True
    assert argument.default is True


def test_list_argument_uses_list_shape(parser: Argparser):
    parser.add_command(function_list_int)

    schema = parser.build_parser_schema()
    command = schema.commands["function-list-int"]
    argument = command.parameters[0]

    assert argument.flags == ("values",)
    assert argument.value_shape is ValueShape.LIST
    assert argument.nargs == "*"
    assert callable(argument.parser)


def test_bound_method_command_omits_initializer(parser: Argparser):
    math = Math(rounding=2)
    parser.add_command(math.pow)

    schema = parser.build_parser_schema()
    command_pow = schema.commands["pow"]

    assert command_pow.initializer == []
    assert [arg.display_name for arg in command_pow.parameters] == ["base", "exponent"]
    assert command_pow.raw_description == doc_summary(Math.pow)


def test_multi_command_records_aliases_and_pipe_targets():
    parser = Argparser(
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        sys_exit_enabled=False,
        help_layout=None,
        pipe_targets="result",
    )
    parser.add_command(pow, aliases=("p",))
    parser.add_command(function_bool_default_true, name="booler")

    schema = parser.build_parser_schema()
    assert schema.is_multi_command is True
    assert schema.pipe_targets is not None
    assert list(schema.pipe_targets.targets) == ["result"]
    assert schema.commands_help and "commands:" in schema.commands_help

    command_pow = schema.commands["pow"]
    assert command_pow.aliases == ("p",)
    assert command_pow.pipe_targets is None

    command_bool = schema.commands["booler"]
    assert command_bool.aliases == ()


def test_command_pipe_targets_flagged_on_arguments(parser: Argparser):
    parser.add_command(pow, pipe_targets="base")

    schema = parser.build_parser_schema()
    command = schema.commands["pow"]

    base_arg = command.parameters[0]
    assert base_arg.name == "base"
    assert base_arg.accepts_stdin is True
    assert base_arg.pipe_required is True
    assert base_arg.required is False
    assert base_arg.nargs == "?"

    exponent_arg = command.parameters[1]
    assert exponent_arg.accepts_stdin is False


def test_enum_argument_populates_choices(parser: Argparser):
    parser.add_command(function_enum_arg)

    schema = parser.build_parser_schema()
    command = schema.commands["function-enum-arg"]
    argument = command.parameters[0]

    assert argument.choices == tuple(member.name for member in Color)
    assert argument.flags == ("color",)
    assert argument.kind is ArgumentKind.POSITIONAL


def test_keyword_only_strategy_keeps_argument_metadata():
    parser = Argparser(
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        sys_exit_enabled=False,
        help_layout=None,
    )
    parser.add_command(pow)

    schema = parser.build_parser_schema()
    command = schema.commands["pow"]
    flags = [argument.flags for argument in command.parameters]

    assert flags[0] == ("-b", "--base")
    assert flags[1] == ("-e", "--exponent")


def test_boolean_short_flag_has_no_negative_form(parser: Argparser):
    parser.add_command(function_bool_short_flag)

    schema = parser.build_parser_schema()
    argument = schema.commands["function-bool-short-flag"].parameters[0]

    assert argument.flags == ("-x",)
    assert argument.boolean_behavior is not None
    assert argument.boolean_behavior.supports_negative is False
    assert argument.boolean_behavior.negative_form is None


def test_optional_list_argument_metadata(parser: Argparser):
    parser.add_command(function_list_with_default)

    schema = parser.build_parser_schema()
    argument = schema.commands["function-list-with-default"].parameters[0]

    assert argument.flags == ("-v", "--values")
    assert argument.value_shape is ValueShape.LIST
    assert argument.nargs == "*"
    assert argument.default == [1, 2]

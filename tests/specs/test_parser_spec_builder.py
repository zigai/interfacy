import inspect

import pytest

from interfacy.argparse_backend import Argparser
from interfacy.naming import DefaultFlagStrategy
from interfacy.schema.schema import ArgumentKind, ValueShape
from tests.conftest import (
    Color,
    Math,
    fn_bool_default_true,
    fn_bool_short_flag,
    fn_enum_arg,
    fn_list_int,
    fn_list_with_default,
    pow,
)


def fn_optional_list_union(values: list[int] | None):
    return values or []


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
    """Verify that function-based commands include both positional and optional arguments."""
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
    """Verify that class-based commands expose initializer parameters and subcommands."""
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
    """Verify that boolean arguments are annotated with correct boolean behavior metadata."""
    parser.add_command(fn_bool_default_true)

    schema = parser.build_parser_schema()
    command = schema.commands["fn-bool-default-true"]
    argument = command.parameters[0]

    assert argument.flags == ("-nv", "--value")
    assert argument.value_shape is ValueShape.FLAG
    assert argument.boolean_behavior is not None
    assert argument.boolean_behavior.supports_negative is True
    assert argument.boolean_behavior.negative_form == "--no-value"
    assert argument.boolean_behavior.default is True
    assert argument.default is True


def test_list_argument_uses_list_shape(parser: Argparser):
    """Verify that list type arguments use the LIST value shape."""
    parser.add_command(fn_list_int)

    schema = parser.build_parser_schema()
    command = schema.commands["fn-list-int"]
    argument = command.parameters[0]

    assert argument.flags == ("values",)
    assert argument.value_shape is ValueShape.LIST
    assert argument.nargs == "*"
    assert callable(argument.parser)


def test_bound_method_command_omits_initializer(parser: Argparser):
    """Verify that commands from bound methods omit the class initializer."""
    math = Math(rounding=2)
    parser.add_command(math.pow)

    schema = parser.build_parser_schema()
    command_pow = schema.commands["pow"]

    assert command_pow.initializer == []
    assert [arg.display_name for arg in command_pow.parameters] == ["base", "exponent"]
    assert command_pow.raw_description == doc_summary(Math.pow)


def test_multi_command_records_aliases_and_pipe_targets():
    """Verify that multi-command specs record aliases and pipe targets correctly."""
    parser = Argparser(
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        sys_exit_enabled=False,
        help_layout=None,
        pipe_targets="result",
    )
    parser.add_command(pow, aliases=("p",))
    parser.add_command(fn_bool_default_true, name="booler")

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
    """Verify that pipe targets are correctly flagged on specific arguments."""
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
    """Verify that Enum arguments populate choices from Enum members."""
    parser.add_command(fn_enum_arg)

    schema = parser.build_parser_schema()
    command = schema.commands["fn-enum-arg"]
    argument = command.parameters[0]

    assert argument.choices == tuple(member.name for member in Color)
    assert argument.flags == ("color",)
    assert argument.kind is ArgumentKind.POSITIONAL


def test_keyword_only_strategy_keeps_argument_metadata():
    """Verify that the keyword-only strategy preserves argument metadata."""
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
    """Verify that boolean arguments with only short flags do not support negative forms."""
    parser.add_command(fn_bool_short_flag)

    schema = parser.build_parser_schema()
    argument = schema.commands["fn-bool-short-flag"].parameters[0]

    assert argument.flags == ("-x",)
    assert argument.boolean_behavior is not None
    assert argument.boolean_behavior.supports_negative is False
    assert argument.boolean_behavior.negative_form is None


def test_optional_list_argument_metadata(parser: Argparser):
    """Verify metadata for optional list arguments with defaults."""
    parser.add_command(fn_list_with_default)

    schema = parser.build_parser_schema()
    argument = schema.commands["fn-list-with-default"].parameters[0]

    assert argument.flags == ("-v", "--values")
    assert argument.value_shape is ValueShape.LIST
    assert argument.nargs == "*"
    assert argument.default == [1, 2]


class TestOptionalUnionListArg:
    """Optional list annotations, eg. list | None, should still behave like lists"""

    def test_optional_union_list_argument_detected_as_list(self, parser: Argparser):
        """Verify that Optional[List] union arguments are detected as lists."""
        parser.add_command(fn_optional_list_union)

        schema = parser.build_parser_schema()
        argument = schema.commands["fn-optional-list-union"].parameters[0]

        assert argument.value_shape is ValueShape.LIST
        assert argument.nargs == "*"

        assert parser.parse_args(["1"])["values"] == [1]
        assert parser.parse_args(["1", "2"])["values"] == [1, 2]
        assert parser.parse_args([])["values"] == []

    def test_optional_union_list_parsed_correctly(self, parser: Argparser):
        """Verify correct parsing of Optional[List] union arguments."""
        parser.add_command(fn_optional_list_union)
        assert parser.parse_args(["1"])["values"] == [1]
        assert parser.parse_args(["1", "2"])["values"] == [1, 2]
        assert parser.parse_args([])["values"] == []

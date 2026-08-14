import inspect

import pytest

from interfacy import BooleanMode, Interfacy, Param, params
from interfacy.naming import DefaultFlagStrategy
from interfacy.schema.schema import ArgumentKind, ValueShape
from tests.fixtures.classes import Math
from tests.fixtures.commands import (
    fn_bool_default_true,
    fn_bool_short_flag,
    fn_enum_arg,
    fn_list_int,
    fn_list_with_default,
    pow,
)
from tests.fixtures.models import Color


def fn_optional_list_union(values: list[int] | None):
    return values or []


def fn_union_list_and_scalar(values: list[int] | str | None):
    return values


@params(alpha=Param(short=False), amount=Param(short=False), active=Param(short=False))
def fn_long_only_flags(
    alpha: bool = False,
    amount: bool = False,
    active: bool = False,
    archive: str = "default",
) -> tuple[str, bool, bool, bool]:
    return archive, alpha, amount, active


def fn_custom_output_format(output_format: str = "text") -> str:
    return output_format


@params(config=Param(kind="positional", metavar="CONFIG"))
def fn_validate_config(config: str | None = None) -> str | None:
    return config


@params(values=Param(kind="positional"))
def fn_optional_positional_values(values: list[int] | None = None) -> list[int]:
    return values or []


@params(value=Param(kind="option"))
def fn_required_option(value: str) -> str:
    return value


def doc_summary(obj) -> str | None:
    doc = inspect.getdoc(obj)
    if not doc:
        return None

    return doc.splitlines()[0]


@pytest.fixture
def parser():
    return Interfacy(
        backend="argparse",
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        help_layout=None,
    )


def test_function_command_includes_positional_and_option(parser: Interfacy):
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
    assert base_arg.argument_default.is_set is False
    assert base_arg.type is int
    assert callable(base_arg.parser)

    exponent_arg = command.parameters[1]
    assert exponent_arg.display_name == "exponent"
    assert exponent_arg.flags == ("-e", "--exponent")
    assert exponent_arg.kind is ArgumentKind.OPTION
    assert exponent_arg.value_shape is ValueShape.SINGLE
    assert exponent_arg.required is False
    assert exponent_arg.argument_default.value == 2
    assert exponent_arg.metavar is None
    assert exponent_arg.type is int
    assert callable(exponent_arg.parser)


def test_class_command_exposes_initializer_and_subcommands(parser: Interfacy):
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
    assert rounding_arg.argument_default.value == 6
    assert rounding_arg.type is int
    assert rounding_arg.metavar is None

    assert command.subcommands is not None
    assert set(command.subcommands) == {"add", "pow", "subtract"}

    pow_command = command.subcommands["pow"]
    assert pow_command.cli_name == "pow"
    assert [arg.display_name for arg in pow_command.parameters] == ["base", "exponent"]


def test_boolean_argument_annotated_with_boolean_behavior(parser: Interfacy):
    """Verify that boolean arguments are annotated with correct boolean behavior metadata."""
    parser.add_command(fn_bool_default_true)

    schema = parser.build_parser_schema()
    command = schema.commands["fn-bool-default-true"]
    argument = command.parameters[0]

    assert argument.flags == ("-n", "--value")
    assert argument.value_shape is ValueShape.FLAG
    assert argument.boolean_behavior is not None
    assert argument.boolean_behavior.positive_flags == ()
    assert argument.boolean_behavior.negative_flags == ("--no-value",)
    assert argument.boolean_behavior.mode is BooleanMode.NEGATIVE_ONLY
    assert argument.boolean_behavior.default is True
    assert argument.argument_default.value is True


def test_boolean_negative_prefix_can_be_configured() -> None:
    parser = Interfacy(
        backend="argparse",
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        help_layout=None,
        bool_negative_prefix="without-",
    )
    parser.add_command(fn_bool_default_true)

    schema = parser.build_parser_schema()
    argument = schema.commands["fn-bool-default-true"].parameters[0]

    assert argument.boolean_behavior is not None
    assert argument.boolean_behavior.negative_flags == ("--without-value",)
    assert parser.invoke(args=["--without-value"]) is False


def test_list_argument_uses_list_shape(parser: Interfacy):
    """Verify that list type arguments use the LIST value shape."""
    parser.add_command(fn_list_int)

    schema = parser.build_parser_schema()
    command = schema.commands["fn-list-int"]
    argument = command.parameters[0]

    assert argument.flags == ("values",)
    assert argument.value_shape is ValueShape.LIST
    assert argument.cardinality.minimum_values == 1
    assert argument.cardinality.maximum_values is None
    assert callable(argument.parser)


def test_bound_method_command_omits_initializer(parser: Interfacy):
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
    parser = Interfacy(
        backend="argparse",
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        help_layout=None,
        pipe_targets="result",
    )
    parser.add_command(pow, aliases=("p",))
    parser.add_command(fn_bool_default_true, name="booler")

    schema = parser.build_parser_schema()
    assert schema.is_multi_command is True
    assert schema.pipe_targets is not None
    assert list(schema.pipe_targets.targets) == ["result"]
    assert schema.canonical_names == ("pow", "booler")

    command_pow = schema.commands["pow"]
    assert command_pow.aliases == ("p",)
    assert command_pow.pipe_targets is None

    command_bool = schema.commands["booler"]
    assert command_bool.aliases == ()


def test_command_pipe_targets_flagged_on_arguments(parser: Interfacy):
    """Verify that pipe targets are correctly flagged on specific arguments."""
    parser.add_command(pow, pipe_targets="base")

    schema = parser.build_parser_schema()
    command = schema.commands["pow"]

    base_arg = command.parameters[0]
    assert base_arg.name == "base"
    assert base_arg.accepts_stdin is True
    assert base_arg.pipe_required is True
    assert base_arg.required is False
    assert base_arg.cardinality.minimum_values == 0
    assert base_arg.cardinality.maximum_values == 1

    exponent_arg = command.parameters[1]
    assert exponent_arg.accepts_stdin is False


def test_enum_argument_populates_choices(parser: Interfacy):
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
    parser = Interfacy(
        backend="argparse",
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        help_layout=None,
    )
    parser.add_command(pow)

    schema = parser.build_parser_schema()
    command = schema.commands["pow"]
    flags = [argument.flags for argument in command.parameters]

    assert flags[0] == ("-b", "--base")
    assert flags[1] == ("-e", "--exponent")


def test_param_short_false_keeps_later_short_flags_available(parser: Interfacy) -> None:
    parser.add_command(fn_long_only_flags)

    schema = parser.build_parser_schema()
    command = schema.commands["fn-long-only-flags"]
    flags = {argument.name: argument.flags for argument in command.parameters}

    assert flags["alpha"] == ("--alpha",)
    assert flags["amount"] == ("--amount",)
    assert flags["active"] == ("--active",)
    assert flags["archive"] == ("-a", "--archive")


def test_add_command_parameter_settings_can_override_flags(parser: Interfacy) -> None:
    parser.add_command(
        fn_custom_output_format,
        parameter_settings={"output_format": Param(long="style", short="s")},
    )

    schema = parser.build_parser_schema()
    argument = schema.commands["fn-custom-output-format"].parameters[0]

    assert argument.flags == ("-s", "--style")
    assert parser.invoke(args=["--style", "json"]) == "json"


def test_param_can_override_help_and_metavar(parser: Interfacy) -> None:
    parser.add_command(
        fn_custom_output_format,
        parameter_settings={
            "output_format": Param(help="Output rendering format.", metavar="FORMAT"),
        },
    )

    argument = parser.build_parser_schema().commands["fn-custom-output-format"].parameters[0]

    assert argument.help == "Output rendering format."
    assert argument.metavar == "FORMAT"


def test_param_kind_positional_makes_defaulted_scalar_positional(parser: Interfacy) -> None:
    parser.add_command(fn_validate_config, name="validate")

    argument = parser.build_parser_schema().commands["validate"].parameters[0]

    assert argument.name == "config"
    assert argument.kind is ArgumentKind.POSITIONAL
    assert argument.flags == ("config",)
    assert argument.required is False
    assert argument.argument_default.value is None
    assert argument.cardinality.minimum_values == 0
    assert argument.cardinality.maximum_values == 1
    assert argument.metavar == "CONFIG"


def test_param_kind_positional_makes_optional_list_positional(parser: Interfacy) -> None:
    parser.add_command(fn_optional_positional_values)

    argument = parser.build_parser_schema().commands["fn-optional-positional-values"].parameters[0]

    assert argument.kind is ArgumentKind.POSITIONAL
    assert argument.value_shape is ValueShape.LIST
    assert argument.required is False
    assert argument.cardinality.minimum_values == 0
    assert argument.cardinality.maximum_values is None


def test_param_kind_option_makes_required_value_an_option(parser: Interfacy) -> None:
    parser.add_command(fn_required_option)

    argument = parser.build_parser_schema().commands["fn-required-option"].parameters[0]

    assert argument.kind is ArgumentKind.OPTION
    assert argument.flags == ("-v", "--value")
    assert argument.required is True


def test_boolean_false_default_exposes_only_positive_long_form(parser: Interfacy):
    parser.add_command(fn_bool_short_flag)

    schema = parser.build_parser_schema()
    argument = schema.commands["fn-bool-short-flag"].parameters[0]

    assert argument.flags == ("--x",)
    assert argument.boolean_behavior is not None
    assert argument.boolean_behavior.positive_flags == ("--x",)
    assert argument.boolean_behavior.negative_flags == ()
    assert argument.boolean_behavior.mode is BooleanMode.POSITIVE_ONLY


def test_optional_list_argument_metadata(parser: Interfacy):
    """Verify metadata for optional list arguments with defaults."""
    parser.add_command(fn_list_with_default)

    schema = parser.build_parser_schema()
    argument = schema.commands["fn-list-with-default"].parameters[0]

    assert argument.flags == ("-v", "--values")
    assert argument.value_shape is ValueShape.LIST
    assert argument.cardinality.minimum_values == 0
    assert argument.cardinality.maximum_values is None
    assert argument.argument_default.value == [1, 2]


class TestOptionalUnionListArg:
    """Optional list annotations, eg. list | None, should still behave like lists."""

    def test_optional_union_list_argument_detected_as_list(self, parser: Interfacy):
        """Verify that Optional[List] union arguments are detected as lists."""
        parser.add_command(fn_optional_list_union)

        schema = parser.build_parser_schema()
        argument = schema.commands["fn-optional-list-union"].parameters[0]

        assert argument.value_shape is ValueShape.LIST
        assert argument.cardinality.minimum_values == 0
        assert argument.cardinality.maximum_values is None

        assert parser.parse_args(["1"])["values"] == [1]
        assert parser.parse_args(["1", "2"])["values"] == [1, 2]
        assert parser.parse_args([])["values"] == []

    def test_optional_union_list_parsed_correctly(self, parser: Interfacy):
        """Verify correct parsing of Optional[List] union arguments."""
        parser.add_command(fn_optional_list_union)
        assert parser.parse_args(["1"])["values"] == [1]
        assert parser.parse_args(["1", "2"])["values"] == [1, 2]
        assert parser.parse_args([])["values"] == []


def test_list_union_with_additional_types_is_not_treated_as_optional_list(parser: Interfacy):
    """Verify list | X | None remains a scalar union and not nargs='*'."""
    parser.add_command(fn_union_list_and_scalar)

    schema = parser.build_parser_schema()
    argument = schema.commands["fn-union-list-and-scalar"].parameters[0]

    assert argument.value_shape is ValueShape.SINGLE
    assert argument.cardinality.minimum_values == 1
    assert argument.cardinality.maximum_values == 1
    assert argument.type == list[int] | str | None

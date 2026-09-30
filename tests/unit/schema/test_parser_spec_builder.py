import pytest

from interfacy import Interfacy, Param, params
from interfacy.naming import DefaultFlagStrategy
from tests.fixtures.commands import fn_bool_default_true


def fn_optional_list_union(values: list[int] | None):
    return values or []


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


@pytest.fixture
def parser():
    return Interfacy(
        backend="argparse",
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        help_layout=None,
    )


def test_boolean_negative_prefix_can_be_configured() -> None:
    parser = Interfacy(
        backend="argparse",
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        help_layout=None,
        bool_negative_prefix="without-",
    )
    parser.add_command(fn_bool_default_true)

    assert parser.invoke(args=[]) is True
    assert parser.invoke(args=["--without-value"]) is False


def test_param_short_false_keeps_later_short_flags_available(parser: Interfacy) -> None:
    parser.add_command(fn_long_only_flags)

    schema = parser.build_parser_schema()
    command = schema.commands["fn-long-only-flags"]
    flags = {argument.name: argument.flags for argument in command.parameters}

    assert flags["alpha"] == ("--alpha",)
    assert flags["amount"] == ("--amount",)
    assert flags["active"] == ("--active",)
    assert flags["archive"] == ("-a", "--archive")


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


class TestOptionalUnionListArg:
    """Optional list annotations, eg. list | None, should still behave like lists."""

    def test_optional_union_list_parsed_correctly(self, parser: Interfacy):
        """Verify correct parsing of Optional[List] union arguments."""
        parser.add_command(fn_optional_list_union)
        assert parser.parse_args(["1"])["values"] == [1]
        assert parser.parse_args(["1", "2"])["values"] == [1, 2]
        assert parser.parse_args([])["values"] == []

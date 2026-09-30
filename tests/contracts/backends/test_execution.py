import pytest

from interfacy import DuplicatePluginError, Interfacy
from interfacy.exceptions import UsageError
from interfacy.plugins import InterfacyPlugin
from tests.fixtures.classes import Math
from tests.fixtures.commands import (
    fn_bool_default_false,
    fn_bool_default_true,
    fn_bool_required,
    fn_enum_arg,
    fn_list_int,
    fn_literal_arg,
    fn_two_lists,
    pow,
)
from tests.fixtures.models import Color


class TestPowFunctionParsing:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_default_exponent(self, parser: Interfacy):
        """Verify execution of command with default values."""
        parser.add_command(pow)
        assert parser.invoke(args=["2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_positional(self, parser: Interfacy):
        """Verify execution of command with provided positional/option arguments."""
        parser.add_command(pow)
        assert parser.invoke(args=["2", "-e", "4"]) == 16

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_kw_only_abbrev(self, parser: Interfacy):
        """Verify execution of keyword-only arguments using short flags."""
        parser.add_command(pow)
        assert parser.invoke(args=["-b", "2", "-e", "4"]) == 16

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_kw_only_no_abbrev(self, parser: Interfacy):
        """Verify execution of keyword-only arguments using long flags."""
        parser.add_command(pow)
        assert parser.invoke(args=["--base", "2", "--exponent", "4"]) == 16


class TestParserReuse:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_run_can_be_called_twice_with_same_inline_command(self, parser: Interfacy):
        """Reusing one parser instance across repeated run() calls should be stable."""

        def greet_once(name: str) -> str:
            return f"hello {name}"

        assert parser.invoke(greet_once, args=["Ada"]) == "hello Ada"
        assert parser.invoke(greet_once, args=["Ada"]) == "hello Ada"

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_inline_run_restores_registered_commands(
        self,
        parser: Interfacy,
    ):
        """Inline run() commands should not replace existing registrations."""

        def persistent(name: str) -> str:
            return f"persisted {name}"

        def temporary() -> str:
            return "temporary"

        parser.add_command(persistent)
        parser.build_parser()

        result = parser.invoke(temporary, args=["temporary"])

        assert result == "temporary"
        assert [command.canonical_name for command in parser.get_commands()] == ["persistent"]
        assert parser.invoke(args=["Ada"]) == "persisted Ada"

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_inline_run_restores_state_after_parse_failure(self, parser: Interfacy):
        """Failed inline parsing should leave existing parser registrations intact."""

        def persistent(name: str) -> str:
            return f"persisted {name}"

        def temporary(name: str) -> str:
            return f"temporary {name}"

        parser.add_command(persistent)
        parser.build_parser()

        with pytest.raises(UsageError):
            parser.invoke(temporary, args=["temporary"])

        assert [command.canonical_name for command in parser.get_commands()] == ["persistent"]
        assert parser.invoke(args=["Ada"]) == "persisted Ada"
        parser.add_command(temporary)
        assert parser.invoke(args=["temporary", "Ada"]) == "temporary Ada"

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_inline_run_restores_plugins_and_pipe_overrides_after_runtime_failure(
        self,
        parser: Interfacy,
        pipe_stdin,
    ):
        """Runtime failures should not discard parser-level plugins or pipe settings."""

        class MarkerPlugin(InterfacyPlugin):
            name = "marker"

        def persistent(name: str) -> str:
            return name

        def boom() -> None:
            raise ValueError("boom")

        plugin = MarkerPlugin()
        parser.add_plugin(plugin)
        parser.add_command(persistent, pipe_targets="name")
        pipe_stdin("piped")

        with pytest.raises(ValueError, match="boom"):
            parser.invoke(boom, args=["boom"])

        with pytest.raises(DuplicatePluginError):
            parser.add_plugin(plugin)

        assert parser.invoke(args=[]) == "piped"


class TestMathClassParsing:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_from_class(self, parser: Interfacy):
        """Verify execution of commands derived from class methods and init parameters."""
        parser.add_command(Math)
        assert parser.invoke(args=["pow", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_from_instance(self, parser: Interfacy):
        """Verify execution of commands derived from instance methods."""
        math = Math(rounding=2)
        parser.add_command(math)  # type: ignore[arg-type]

        assert parser.invoke(args=["pow", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_from_instance_method(self, parser: Interfacy):
        """Verify execution of a specific bound method as a command."""
        math = Math(rounding=2)
        parser.add_command(math.pow)

        assert parser.invoke(args=["2", "-e", "4"]) == 16


class TestMultipleCommands:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_from_multiple_pow(self, parser: Interfacy):
        """Verify multiple command execution (routing to 'pow') with specific target commands."""
        parser.add_command(pow)
        parser.add_command(Math)

        assert parser.invoke(args=["pow", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_from_multiple_math(self, parser: Interfacy):
        """Verify multiple command execution (routing to 'math') with specific target commands."""
        parser.add_command(pow)
        parser.add_command(Math)

        assert parser.invoke(args=["math", "pow", "2", "-e", "2"]) == 4


class TestBooleanFlags:
    @pytest.mark.parametrize(
        "parser",
        ["argparse_req_pos", "argparse_kw_only", "click_req_pos", "click_kw_only"],
        indirect=True,
    )
    def test_bool_required(self, parser: Interfacy):
        """Verify execution with required boolean flags."""
        parser.add_command(fn_bool_required)
        assert parser.invoke(args=["--value"]) is True
        assert parser.invoke(args=["--no-value"]) is False

    @pytest.mark.parametrize(
        "parser",
        ["argparse_req_pos", "argparse_kw_only", "click_req_pos", "click_kw_only"],
        indirect=True,
    )
    def test_bool_default_true(self, parser: Interfacy):
        """Verify execution with boolean flags defaulting to True."""
        parser.add_command(fn_bool_default_true)

        assert parser.invoke(args=[]) is True
        assert parser.invoke(args=["--no-value"]) is False

    @pytest.mark.parametrize(
        "parser",
        ["argparse_req_pos", "argparse_kw_only", "click_req_pos", "click_kw_only"],
        indirect=True,
    )
    def test_bool_false_by_default(self, parser: Interfacy):
        """Verify execution with boolean flags defaulting to False."""
        parser.add_command(fn_bool_default_false)

        assert parser.invoke(args=[]) is False
        assert parser.invoke(args=["--value"]) is True

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_negative_named_bool_is_one_way_flag(self, parser: Interfacy):
        def run(*, no_stdio: bool = False) -> bool:
            return no_stdio

        parser.add_command(run)

        assert parser.invoke(args=[]) is False
        assert parser.invoke(args=["--no-stdio"]) is True

        with pytest.raises(UsageError):
            parser.invoke(args=["--stdio"])


class TestEnums:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_enum_positional(self, parser: Interfacy):
        """Verify execution mapping Enum arguments from positional input."""
        parser.add_command(fn_enum_arg)
        assert parser.invoke(args=["RED"]) == Color.RED

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_enum_kwarg(self, parser: Interfacy):
        """Verify execution mapping Enum arguments from flag input."""
        parser.add_command(fn_enum_arg)
        assert parser.invoke(args=["-c", "RED"]) == Color.RED


class TestLiterals:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_literal_positional(self, parser: Interfacy):
        """Verify execution mapping Literal arguments from positional input."""
        parser.add_command(fn_literal_arg)
        assert parser.invoke(args=["RED"]) == "RED"

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_literal_positional_invalid_value_raises_usage_error(self, parser: Interfacy):
        """Verify invalid Literal positional input raises a usage error."""
        parser.add_command(fn_literal_arg)
        with pytest.raises(UsageError):
            parser.invoke(args=["PURPLE"])

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_literal_positional_missing_required_raises_usage_error(self, parser: Interfacy):
        """Verify missing required Literal positional input raises a usage error."""
        parser.add_command(fn_literal_arg)
        with pytest.raises(UsageError):
            parser.invoke(args=[])

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_literal_kw_only_missing_required_raises_usage_error(self, parser: Interfacy):
        """Verify missing required Literal option raises a usage error."""
        parser.add_command(fn_literal_arg)
        with pytest.raises(UsageError):
            parser.invoke(args=[])


class TestListNargs:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_list_nargs(self, parser: Interfacy):
        """Verify execution collecting multiple arguments into a list."""
        parser.add_command(fn_list_int)
        assert parser.invoke(args=["1", "2", "3"]) == [1, 2, 3]

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_list_two_positional(self, parser: Interfacy):
        """Verify execution collecting multiple lists."""
        parser.add_command(fn_two_lists)
        assert parser.invoke(args=["a", "b", "--ints", "1", "2"]) == (2, 2)


class TestCustomCommandNames:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_custom_command_names(self, parser: Interfacy):
        """Verify execution respects custom command names."""
        parser.add_command(Math, name="command1")
        parser.add_command(pow, name="command2")
        assert parser.invoke(args=["command2", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_custom_command_names_with_hyphen(self, parser: Interfacy):
        """Verify execution respects custom command names with hyphens."""
        parser.add_command(Math, name="command-1")
        parser.add_command(pow, name="command-2")
        assert parser.invoke(args=["command-2", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_custom_command_names_uppercase(self, parser: Interfacy):
        """Verify execution respects uppercase custom command names."""
        parser.add_command(Math, name="COMMAND1")
        parser.add_command(pow, name="COMMAND2")
        assert parser.invoke(args=["COMMAND2", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_custom_command_names_with_underscore(self, parser: Interfacy):
        """Verify execution respects custom command names with underscores."""
        parser.add_command(Math, name="command_1")
        parser.add_command(pow, name="command_2")
        assert parser.invoke(args=["command_2", "2", "-e", "2"]) == 4


class TestMathClassParsingKwOnly:
    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_from_class(self, parser: Interfacy):
        """Verify class-based command execution with kw-only strategy."""
        parser.add_command(Math)
        assert parser.invoke(args=["pow", "--base", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_from_instance(self, parser: Interfacy):
        """Verify instance-based command execution with kw-only strategy."""
        math = Math(rounding=2)
        parser.add_command(math)  # type: ignore[arg-type]

        assert parser.invoke(args=["pow", "--base", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_from_instance_method(self, parser: Interfacy):
        """Verify bound method execution with kw-only strategy."""
        math = Math(rounding=2)
        parser.add_command(math.pow)

        assert parser.invoke(args=["--base", "2", "-e", "4"]) == 16


class TestMultipleCommandsKwOnly:
    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_from_multiple_pow(self, parser: Interfacy):
        """Verify multiple command execution (routing to 'pow') with kw-only strategy."""
        parser.add_command(pow)
        parser.add_command(Math)

        assert parser.invoke(args=["pow", "--base", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_from_multiple_math(self, parser: Interfacy):
        """Verify multiple command execution (routing to 'math') with kw-only strategy."""
        parser.add_command(pow)
        parser.add_command(Math)

        # Note: Math(rounding=...) is init arg. For argparse_kw_only, it should be a flag.
        # But Math init defaults to 6. Here we rely on default?
        # args=["math", "pow", ...] invokes math command, then pow subcommand.
        # Does math command accept flags for init? Yes.
        # args=["math", "pow", "--base", "2", "-e", "2"]
        assert parser.invoke(args=["math", "pow", "--base", "2", "-e", "2"]) == 4


class TestListNargsKwOnly:
    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_list_nargs(self, parser: Interfacy):
        """Verify list argument execution with kw-only strategy."""
        parser.add_command(fn_list_int)
        # For kw_only, list argument 'values' becomes --values [v1 v2 ...]
        assert parser.invoke(args=["--values", "1", "2", "3"]) == [1, 2, 3]

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_list_two_lists(self, parser: Interfacy):
        """Verify execution of multiple list arguments with kw-only strategy."""
        parser.add_command(fn_two_lists)
        # strings: list[str], ints: list[int]
        # kw_only -> --strings a b --ints 1 2
        assert parser.invoke(args=["--strings", "a", "b", "--ints", "1", "2"]) == (2, 2)


class TestStressRegressionExecution:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_optional_fixed_tuple_keeps_tuple_shape(self, parser: Interfacy):
        def command(pair: tuple[int, str] | None = None):
            return pair

        parser.add_command(command)

        assert parser.invoke(args=["--pair", "1", "a"]) == (1, "a")

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_union_of_lists_keeps_list_shape(self, parser: Interfacy):
        def command(values: list[int] | list[str]):
            return values

        parser.add_command(command)

        assert parser.invoke(args=["1", "2"]) == [1, 2]

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_translated_positional_name_binds_to_original_parameter(
        self,
        parser: Interfacy,
    ):
        def command(XMLHttpRequestID: str) -> str:  # noqa: N803
            return XMLHttpRequestID

        parser.add_command(command)
        assert parser.invoke(args=["ABC"]) == "ABC"

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_translated_unicode_option_name_binds_to_original_parameter(
        self,
        parser: Interfacy,
    ):
        def command(déjàVu: str = "seen") -> str:  # noqa: N803, PLC2401
            return déjàVu

        parser.add_command(command)
        assert parser.invoke(args=["--dé-jà-vu", "D"]) == "D"

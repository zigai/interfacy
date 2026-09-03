import pytest

from interfacy import Interfacy
from interfacy.exceptions import UsageError
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
        """Verify correct parsing of default values for positional and option arguments."""
        parser.add_command(pow)
        args = parser.parse_args(["2"])
        assert args == {"base": 2, "exponent": 2}

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_positional(self, parser: Interfacy):
        """Verify parsing of arguments passed as positionals or options."""
        parser.add_command(pow)
        args = parser.parse_args(["2", "-e", "4"])
        assert args == {"base": 2, "exponent": 4}

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_kw_only_abbrev(self, parser: Interfacy):
        """Verify parsing of keyword-only arguments using short flags."""
        parser.add_command(pow)
        args = parser.parse_args(["-b", "2", "-e", "4"])
        assert args == {"base": 2, "exponent": 4}

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_kw_only_no_abbrev(self, parser: Interfacy):
        """Verify parsing of keyword-only arguments using long flags."""
        parser.add_command(pow)
        args = parser.parse_args(["--base", "2", "--exponent", "4"])
        assert args == {"base": 2, "exponent": 4}

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_kw_only_abbrev_collision_skips_second_short(self, parser: Interfacy):
        """Verify that short-flag collisions do not fall back to multi-character aliases."""

        def fn_collision(*, value: int = 1, version: int = 2) -> tuple[int, int]:
            return value, version

        parser.add_command(fn_collision)
        args = parser.parse_args(["-v", "3", "--version", "4"])
        assert args == {"value": 3, "version": 4}


class TestMathClassParsing:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_from_class(self, parser: Interfacy):
        """Verify parsing of commands derived from class methods and init parameters."""
        parser.add_command(Math)
        args = parser.parse_args(["pow", "2", "-e", "2"])

        assert args == {
            "command": "pow",
            "rounding": 6,
            "pow": {
                "base": 2,
                "exponent": 2,
            },
        }

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_class_initializer_options_can_follow_subcommand(self, parser: Interfacy):
        """Verify class initializer options are accepted after method arguments."""
        parser.add_command(Math)
        args = parser.parse_args(["pow", "2", "-e", "2", "--rounding", "3"])

        assert args == {
            "command": "pow",
            "rounding": 3,
            "pow": {
                "base": 2,
                "exponent": 2,
            },
        }

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_subcommand_option_takes_precedence_over_initializer_option(
        self,
        parser: Interfacy,
    ):
        """Verify options after a subcommand stay on the nearest command that accepts them."""

        class ModeTool:
            def __init__(self, mode: str = "parent") -> None:
                self.mode = mode

            def run(self, mode: str = "child") -> tuple[str, str]:
                return self.mode, mode

        parser.add_command(ModeTool)
        args = parser.parse_args(["run", "--mode", "leaf"])

        assert args == {
            "command": "run",
            "mode": "parent",
            "run": {"mode": "leaf"},
        }

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_initializer_option_after_subcommand_supports_equals_form(
        self,
        parser: Interfacy,
    ):
        """Verify late initializer options support --option=value syntax."""
        parser.add_command(Math)
        args = parser.parse_args(["pow", "2", "--rounding=3"])

        assert args == {
            "command": "pow",
            "rounding": 3,
            "pow": {
                "base": 2,
                "exponent": 2,
            },
        }

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_initializer_negative_boolean_option_can_follow_subcommand(
        self,
        parser: Interfacy,
    ):
        """Verify late initializer options include generated negative boolean aliases."""

        class ToggleTool:
            def __init__(self, enabled: bool = True) -> None:
                self.enabled = enabled

            def run(self) -> bool:
                return self.enabled

        parser.add_command(ToggleTool)
        args = parser.parse_args(["run", "--no-enabled"])

        assert args == {
            "command": "run",
            "enabled": False,
            "run": {},
        }

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_late_initializer_list_option_stops_before_subcommand_option(
        self,
        parser: Interfacy,
    ):
        """Verify variable-length initializer options do not consume child options."""

        class TagsTool:
            def __init__(self, tags: list[str] | None = None) -> None:
                self.tags = tags

            def run(self, count: int = 1) -> tuple[list[str] | None, int]:
                return self.tags, count

        parser.add_command(TagsTool)
        args = parser.parse_args(["run", "--tags", "a", "b", "--count", "2"])

        assert args == {
            "command": "run",
            "tags": ["a", "b"],
            "run": {"count": 2},
        }

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_required_late_initializer_list_option_is_applied(
        self,
        parser: Interfacy,
    ):
        """Verify required late list initializer options are applied after parsing."""

        class TagsTool:
            def __init__(self, *, tags: list[str]) -> None:
                self.tags = tags

            def run(self) -> list[str]:
                return self.tags

        parser.add_command(TagsTool)
        args = parser.parse_args(["run", "--tags", "a"])

        assert args == {
            "command": "run",
            "tags": ["a"],
            "run": {},
        }

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_typed_late_initializer_list_option_parse_error_uses_argparse(
        self,
        parser: Interfacy,
    ):
        """Verify late list conversion errors use argparse parse handling."""

        class TagsTool:
            def __init__(self, *, tags: list[int] | None = None) -> None:
                self.tags = tags

            def run(self) -> list[int] | None:
                return self.tags

        parser.add_command(TagsTool)

        with pytest.raises(UsageError):
            parser.parse_args(["run", "--tags", "bad"])

    @pytest.mark.parametrize("parser", ["click_kw_only"], indirect=True)
    def test_typed_late_initializer_list_option_parse_error_uses_click(
        self,
        parser: Interfacy,
    ):
        """Verify late list conversion errors use the public usage-error contract."""
        pytest.importorskip("click")

        class TagsTool:
            def __init__(self, *, tags: list[int] | None = None) -> None:
                self.tags = tags

            def run(self) -> list[int] | None:
                return self.tags

        parser.add_command(TagsTool)

        with pytest.raises(UsageError):
            parser.parse_args(["run", "--tags", "bad"])

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_from_instance(self, parser: Interfacy):
        """Verify parsing of commands derived from instance methods."""
        math = Math(rounding=2)
        parser.add_command(math)  # type: ignore[arg-type]

        args = parser.parse_args(["pow", "2", "-e", "2"])
        assert args == {
            "command": "pow",
            "pow": {
                "base": 2,
                "exponent": 2,
            },
        }

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_from_instance_method(self, parser: Interfacy):
        """Verify parsing of a specific bound method as a command."""
        math = Math(rounding=2)
        parser.add_command(math.pow)

        args = parser.parse_args(["2", "-e", "4"])
        assert args == {"base": 2, "exponent": 4}


class TestMultipleCommands:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_from_multiple(self, parser: Interfacy):
        """Verify parsing when multiple commands are registered (subcommand routing)."""
        parser.add_command(pow)
        parser.add_command(Math)

        args = parser.parse_args(["pow", "2", "-e", "2"])
        assert args == {
            "command": "pow",
            "pow": {
                "base": 2,
                "exponent": 2,
            },
        }

        args = parser.parse_args(["math", "pow", "2", "-e", "2"])
        assert args == {
            "command": "math",
            "math": {
                "command": "pow",
                "rounding": 6,
                "pow": {
                    "base": 2,
                    "exponent": 2,
                },
            },
        }

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_nested_class_initializer_options_can_follow_subcommand(
        self,
        parser: Interfacy,
    ):
        """Verify nested class initializer options are accepted after method arguments."""
        parser.add_command(pow)
        parser.add_command(Math)

        args = parser.parse_args(["math", "pow", "2", "-e", "2", "--rounding", "3"])
        assert args == {
            "command": "math",
            "math": {
                "command": "pow",
                "rounding": 3,
                "pow": {
                    "base": 2,
                    "exponent": 2,
                },
            },
        }


class TestBooleanFlags:
    @pytest.mark.parametrize(
        "parser",
        ["argparse_req_pos", "argparse_kw_only", "click_req_pos", "click_kw_only"],
        indirect=True,
    )
    def test_bool_required(self, parser: Interfacy):
        """Verify parsing of required boolean flags."""
        parser.add_command(fn_bool_required)
        args = parser.parse_args(["--value"])
        assert args["value"] is True

        args = parser.parse_args(["--no-value"])
        assert args["value"] is False

    @pytest.mark.parametrize(
        "parser",
        ["argparse_req_pos", "argparse_kw_only", "click_req_pos", "click_kw_only"],
        indirect=True,
    )
    def test_bool_default_true(self, parser: Interfacy):
        """Verify parsing of boolean flags defaulting to True."""
        parser.add_command(fn_bool_default_true)
        args = parser.parse_args([])
        assert args["value"] is True

        args = parser.parse_args(["--no-value"])
        assert args["value"] is False

    @pytest.mark.parametrize(
        "parser",
        ["argparse_req_pos", "argparse_kw_only", "click_req_pos", "click_kw_only"],
        indirect=True,
    )
    def test_bool_false_by_default(self, parser: Interfacy):
        """Verify parsing of boolean flags defaulting to False."""
        parser.add_command(fn_bool_default_false)

        args = parser.parse_args([])
        assert args["value"] is False

        args = parser.parse_args(["--value"])
        assert args["value"] is True

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
        """Verify parsing of Enum arguments from positional input."""
        parser.add_command(fn_enum_arg)
        args = parser.parse_args(["RED"])
        assert args["color"] == Color.RED

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_enum_kwarg(self, parser: Interfacy):
        """Verify parsing of Enum arguments from flag input."""
        parser.add_command(fn_enum_arg)
        args = parser.parse_args(["-c", "RED"])
        assert args["color"] == Color.RED


class TestLiterals:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_literal_positional(self, parser: Interfacy):
        """Verify parsing of Literal arguments from positional input."""
        parser.add_command(fn_literal_arg)
        args = parser.parse_args(["RED"])
        assert args["color"] == "RED"

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_literal_kwarg(self, parser: Interfacy):
        """Verify parsing of Literal arguments from flag input."""
        parser.add_command(fn_literal_arg)
        args = parser.parse_args(["-c", "RED"])
        assert args["color"] == "RED"


class TestListNargs:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_list_nargs(self, parser: Interfacy):
        """Verify parsing of variable length list arguments."""
        parser.add_command(fn_list_int)
        namespace = parser.parse_args(["1", "2", "3"])
        assert namespace["values"] == [1, 2, 3]

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_list_two_positional(self, parser: Interfacy):
        """Verify parsing of multiple list arguments."""
        parser.add_command(fn_two_lists)
        namespace = parser.parse_args(["a", "b", "--ints", "1", "2"])
        assert namespace["strings"] == ["a", "b"]
        assert namespace["ints"] == [1, 2]


class TestCustomCommandNames:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_custom_command_names(self, parser: Interfacy):
        """Verify that custom command names are respected during parsing."""
        parser.add_command(Math, name="command1")
        parser.add_command(pow, name="command2")
        assert parser.invoke(args=["command2", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_custom_command_names_with_hyphen(self, parser: Interfacy):
        """Verify parsing of custom command names containing hyphens."""
        parser.add_command(Math, name="command-1")
        parser.add_command(pow, name="command-2")
        assert parser.invoke(args=["command-2", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_custom_command_names_uppercase(self, parser: Interfacy):
        """Verify parsing of uppercase custom command names."""
        parser.add_command(Math, name="COMMAND1")
        parser.add_command(pow, name="COMMAND2")
        assert parser.invoke(args=["COMMAND2", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_custom_command_names_with_underscore(self, parser: Interfacy):
        """Verify parsing of custom command names containing underscores."""
        parser.add_command(Math, name="command_1")
        parser.add_command(pow, name="command_2")
        assert parser.invoke(args=["command_2", "2", "-e", "2"]) == 4


class TestMathClassParsingKwOnly:
    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_from_class(self, parser: Interfacy):
        """Verify class-based command parsing with kw-only strategy (full flags)."""
        parser.add_command(Math)
        assert parser.invoke(args=["pow", "--base", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_from_instance(self, parser: Interfacy):
        """Verify instance-based command parsing with kw-only strategy."""
        math = Math(rounding=2)
        parser.add_command(math)  # type: ignore[arg-type]

        assert parser.invoke(args=["pow", "--base", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_from_instance_method(self, parser: Interfacy):
        """Verify bound method parsing with kw-only strategy."""
        math = Math(rounding=2)
        parser.add_command(math.pow)

        assert parser.invoke(args=["--base", "2", "-e", "4"]) == 16


class TestMultipleCommandsKwOnly:
    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_from_multiple_pow(self, parser: Interfacy):
        """Verify multiple command parsing (routing to 'pow') with kw-only strategy."""
        parser.add_command(pow)
        parser.add_command(Math)

        assert parser.invoke(args=["pow", "--base", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_from_multiple_math(self, parser: Interfacy):
        """Verify multiple command parsing (routing to 'math') with kw-only strategy."""
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
        """Verify list argument parsing with kw-only strategy (args passed as flags)."""
        parser.add_command(fn_list_int)
        # For kw_only, list argument 'values' becomes --values [v1 v2 ...]
        assert parser.invoke(args=["--values", "1", "2", "3"]) == [1, 2, 3]

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_list_two_lists(self, parser: Interfacy):
        """Verify parsing of multiple list arguments with kw-only strategy."""
        parser.add_command(fn_two_lists)
        # strings: list[str], ints: list[int]
        # kw_only -> --strings a b --ints 1 2
        assert parser.invoke(args=["--strings", "a", "b", "--ints", "1", "2"]) == (2, 2)


class TestStressRegressionParsing:
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

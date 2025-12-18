import pytest

from interfacy.core import InterfacyParser
from tests.conftest import (
    Color,
    Math,
    fn_bool_default_false,
    fn_bool_default_true,
    fn_bool_required,
    fn_enum_arg,
    fn_list_int,
    fn_literal_arg,
    fn_two_lists,
    pow,
)


class TestPowFunctionParsing:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_default_exponent(self, parser: InterfacyParser):
        """Verify correct parsing of default values for positional and option arguments."""
        parser.add_command(pow)
        args = parser.parse_args(["2"])
        assert args == {"base": 2, "exponent": 2}

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_positional(self, parser: InterfacyParser):
        """Verify parsing of arguments passed as positionals or options."""
        parser.add_command(pow)
        args = parser.parse_args(["2", "-e", "4"])
        assert args == {"base": 2, "exponent": 4}

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_kw_only_abbrev(self, parser: InterfacyParser):
        """Verify parsing of keyword-only arguments using short flags."""
        parser.add_command(pow)
        args = parser.parse_args(["-b", "2", "-e", "4"])
        assert args == {"base": 2, "exponent": 4}

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_kw_only_no_abbrev(self, parser: InterfacyParser):
        """Verify parsing of keyword-only arguments using long flags."""
        parser.add_command(pow)
        args = parser.parse_args(["--base", "2", "--exponent", "4"])
        assert args == {"base": 2, "exponent": 4}

    # @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    # def test_kw_only_missing_base(self, parser: InterfacyParserCore):
    #     parser.add_command(pow)
    #     args = parser.parse_args(["-e", "4"])


class TestMathClassParsing:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_from_class(self, parser: InterfacyParser):
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

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_from_instance(self, parser: InterfacyParser):
        """Verify parsing of commands derived from instance methods."""
        math = Math(rounding=2)
        parser.add_command(math)  # type: ignore

        args = parser.parse_args(["pow", "2", "-e", "2"])
        assert args == {
            "command": "pow",
            "pow": {
                "base": 2,
                "exponent": 2,
            },
        }

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_from_instance_method(self, parser: InterfacyParser):
        """Verify parsing of a specific bound method as a command."""
        math = Math(rounding=2)
        parser.add_command(math.pow)

        args = parser.parse_args(["2", "-e", "4"])
        assert args == {"base": 2, "exponent": 4}


class TestMultipleCommands:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_from_multiple(self, parser: InterfacyParser):
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


class TestBooleanFlags:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_bool_required(self, parser: InterfacyParser):
        """Verify parsing of required boolean flags."""
        parser.add_command(fn_bool_required)
        args = parser.parse_args(["--value"])
        assert args["value"] == True

        args = parser.parse_args(["--no-value"])
        assert args["value"] == False

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_bool_default_true(self, parser: InterfacyParser):
        """Verify parsing of boolean flags defaulting to True."""
        parser.add_command(fn_bool_default_true)
        args = parser.parse_args([])
        assert args["value"] == True

        args = parser.parse_args(["--value"])
        assert args["value"] == True

        args = parser.parse_args(["--no-value"])
        assert args["value"] == False

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_bool_false_by_default(self, parser: InterfacyParser):
        """Verify parsing of boolean flags defaulting to False."""
        parser.add_command(fn_bool_default_false)

        args = parser.parse_args([])
        assert args["value"] == False

        args = parser.parse_args(["--value"])
        assert args["value"] == True

        args = parser.parse_args(["--no-value"])
        assert args["value"] == False


class TestEnums:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_enum_positional(self, parser: InterfacyParser):
        """Verify parsing of Enum arguments from positional input."""
        parser.add_command(fn_enum_arg)
        args = parser.parse_args(["RED"])
        assert args["color"] == Color.RED

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_enum_kwarg(self, parser: InterfacyParser):
        """Verify parsing of Enum arguments from flag input."""
        parser.add_command(fn_enum_arg)
        args = parser.parse_args(["-c", "RED"])
        assert args["color"] == Color.RED


class TestLiterals:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_literal_positional(self, parser: InterfacyParser):
        """Verify parsing of Literal arguments from positional input."""
        parser.add_command(fn_literal_arg)
        args = parser.parse_args(["RED"])
        assert args["color"] == "RED"

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_literal_kwarg(self, parser: InterfacyParser):
        """Verify parsing of Literal arguments from flag input."""
        parser.add_command(fn_literal_arg)
        args = parser.parse_args(["-c", "RED"])
        assert args["color"] == "RED"


class TestListNargs:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_list_nargs(self, parser: InterfacyParser):
        """Verify parsing of variable length list arguments."""
        parser.add_command(fn_list_int)
        namespace = parser.parse_args(["1", "2", "3"])
        assert namespace["values"] == [1, 2, 3]

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_list_two_positional(self, parser: InterfacyParser):
        """Verify parsing of multiple list arguments."""
        parser.add_command(fn_two_lists)
        namespace = parser.parse_args(["a", "b", "--ints", "1", "2"])
        assert namespace["strings"] == ["a", "b"]
        assert namespace["ints"] == [1, 2]


class TestCustomCommandNames:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_custom_command_names(self, parser: InterfacyParser):
        """Verify that custom command names are respected during parsing."""
        parser.add_command(Math, name="command1")
        parser.add_command(pow, name="command2")
        assert parser.run(args=["command2", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_custom_command_names_with_hyphen(self, parser: InterfacyParser):
        """Verify parsing of custom command names containing hyphens."""
        parser.add_command(Math, name="command-1")
        parser.add_command(pow, name="command-2")
        assert parser.run(args=["command-2", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_custom_command_names_uppercase(self, parser: InterfacyParser):
        """Verify parsing of uppercase custom command names."""
        parser.add_command(Math, name="COMMAND1")
        parser.add_command(pow, name="COMMAND2")
        assert parser.run(args=["COMMAND2", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_custom_command_names_with_underscore(self, parser: InterfacyParser):
        """Verify parsing of custom command names containing underscores."""
        parser.add_command(Math, name="command_1")
        parser.add_command(pow, name="command_2")
        assert parser.run(args=["command_2", "2", "-e", "2"]) == 4


class TestMathClassParsingKwOnly:
    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_from_class(self, parser: InterfacyParser):
        """Verify class-based command parsing with kw-only strategy (full flags)."""
        parser.add_command(Math)
        assert parser.run(args=["pow", "--base", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_from_instance(self, parser: InterfacyParser):
        """Verify instance-based command parsing with kw-only strategy."""
        math = Math(rounding=2)
        parser.add_command(math)  # type: ignore

        assert parser.run(args=["pow", "--base", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_from_instance_method(self, parser: InterfacyParser):
        """Verify bound method parsing with kw-only strategy."""
        math = Math(rounding=2)
        parser.add_command(math.pow)

        assert parser.run(args=["--base", "2", "-e", "4"]) == 16


class TestMultipleCommandsKwOnly:
    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_from_multiple_pow(self, parser: InterfacyParser):
        """Verify multiple command parsing (routing to 'pow') with kw-only strategy."""
        parser.add_command(pow)
        parser.add_command(Math)

        assert parser.run(args=["pow", "--base", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_from_multiple_math(self, parser: InterfacyParser):
        """Verify multiple command parsing (routing to 'math') with kw-only strategy."""
        parser.add_command(pow)
        parser.add_command(Math)

        # Note: Math(rounding=...) is init arg. For argparse_kw_only, it should be a flag.
        # But Math init defaults to 6. Here we rely on default?
        # args=["math", "pow", ...] invokes math command, then pow subcommand.
        # Does math command accept flags for init? Yes.
        # args=["math", "pow", "--base", "2", "-e", "2"]
        assert parser.run(args=["math", "pow", "--base", "2", "-e", "2"]) == 4


class TestListNargsKwOnly:
    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_list_nargs(self, parser: InterfacyParser):
        """Verify list argument parsing with kw-only strategy (args passed as flags)."""
        parser.add_command(fn_list_int)
        # For kw_only, list argument 'values' becomes --values [v1 v2 ...]
        assert parser.run(args=["--values", "1", "2", "3"]) == [1, 2, 3]

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_list_two_lists(self, parser: InterfacyParser):
        """Verify parsing of multiple list arguments with kw-only strategy."""
        parser.add_command(fn_two_lists)
        # strings: list[str], ints: list[int]
        # kw_only -> --strings a b --ints 1 2
        assert parser.run(args=["--strings", "a", "b", "--ints", "1", "2"]) == (2, 2)

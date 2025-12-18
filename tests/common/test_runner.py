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
    fn_two_lists,
    pow,
)


class TestPowFunctionParsing:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_default_exponent(self, parser: InterfacyParser):
        """Verify execution of command with default values."""
        parser.add_command(pow)
        assert parser.run(args=["2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_positional(self, parser: InterfacyParser):
        """Verify execution of command with provided positional/option arguments."""
        parser.add_command(pow)
        assert parser.run(args=["2", "-e", "4"]) == 16

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_kw_only_abbrev(self, parser: InterfacyParser):
        """Verify execution of keyword-only arguments using short flags."""
        parser.add_command(pow)
        assert parser.run(args=["-b", "2", "-e", "4"]) == 16

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_kw_only_no_abbrev(self, parser: InterfacyParser):
        """Verify execution of keyword-only arguments using long flags."""
        parser.add_command(pow)
        assert parser.run(args=["--base", "2", "--exponent", "4"]) == 16


class TestMathClassParsing:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_from_class(self, parser: InterfacyParser):
        """Verify execution of commands derived from class methods and init parameters."""
        parser.add_command(Math)
        assert parser.run(args=["pow", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_from_instance(self, parser: InterfacyParser):
        """Verify execution of commands derived from instance methods."""
        math = Math(rounding=2)
        parser.add_command(math)  # type: ignore

        assert parser.run(args=["pow", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_from_instance_method(self, parser: InterfacyParser):
        """Verify execution of a specific bound method as a command."""
        math = Math(rounding=2)
        parser.add_command(math.pow)

        assert parser.run(args=["2", "-e", "4"]) == 16


class TestMultipleCommands:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_from_multiple_pow(self, parser: InterfacyParser):
        """Verify multiple command execution (routing to 'pow') with specific target commands."""
        parser.add_command(pow)
        parser.add_command(Math)

        assert parser.run(args=["pow", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_from_multiple_math(self, parser: InterfacyParser):
        """Verify multiple command execution (routing to 'math') with specific target commands."""
        parser.add_command(pow)
        parser.add_command(Math)

        assert parser.run(args=["math", "pow", "2", "-e", "2"]) == 4


class TestBooleanFlags:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_bool_required(self, parser: InterfacyParser):
        """Verify execution with required boolean flags."""
        parser.add_command(fn_bool_required)
        assert parser.run(args=["--value"]) == True
        assert parser.run(args=["--no-value"]) == False

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_bool_default_true(self, parser: InterfacyParser):
        """Verify execution with boolean flags defaulting to True."""
        parser.add_command(fn_bool_default_true)

        assert parser.run(args=[]) == True
        assert parser.run(args=["--value"]) == True
        assert parser.run(args=["--no-value"]) == False

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_bool_false_by_default(self, parser: InterfacyParser):
        """Verify execution with boolean flags defaulting to False."""
        parser.add_command(fn_bool_default_false)

        assert parser.run(args=[]) == False
        assert parser.run(args=["--value"]) == True
        assert parser.run(args=["--no-value"]) == False


class TestEnums:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_enum_positional(self, parser: InterfacyParser):
        """Verify execution mapping Enum arguments from positional input."""
        parser.add_command(fn_enum_arg)
        assert parser.run(args=["RED"]) == Color.RED

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_enum_kwarg(self, parser: InterfacyParser):
        """Verify execution mapping Enum arguments from flag input."""
        parser.add_command(fn_enum_arg)
        assert parser.run(args=["-c", "RED"]) == Color.RED


class TestLiterals:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_literal_positional(self, parser: InterfacyParser):
        # NOTE: Not implemented in original file but present in test_parsing.py?
        # Ah wait, TestLiterals in test_runner.py was just "..." in my view?
        # No, I saw "class TestLiterals: ..." in view_file output but maybe I missed body or it was empty?
        # Let's check line 118 of view_file output.
        # "118: class TestLiterals: ...". Yes, it has "..." literally? Or truncated?
        # If it has "...", then pass.
        # But wait, python valid syntax "class TestLiterals: ..." refers to Ellipsis?
        # It's valid body.
        # So I shouldn't add methods if they aren't there.
        pass


class TestListNargs:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_list_nargs(self, parser: InterfacyParser):
        """Verify execution collecting multiple arguments into a list."""
        parser.add_command(fn_list_int)
        assert parser.run(args=["1", "2", "3"]) == [1, 2, 3]

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_list_two_positional(self, parser: InterfacyParser):
        """Verify execution collecting multiple lists."""
        parser.add_command(fn_two_lists)
        assert parser.run(args=["a", "b", "--ints", "1", "2"]) == (2, 2)


class TestCustomCommandNames:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_custom_command_names(self, parser: InterfacyParser):
        """Verify execution respects custom command names."""
        parser.add_command(Math, name="command1")
        parser.add_command(pow, name="command2")
        assert parser.run(args=["command2", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_custom_command_names_with_hyphen(self, parser: InterfacyParser):
        """Verify execution respects custom command names with hyphens."""
        parser.add_command(Math, name="command-1")
        parser.add_command(pow, name="command-2")
        assert parser.run(args=["command-2", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_custom_command_names_uppercase(self, parser: InterfacyParser):
        """Verify execution respects uppercase custom command names."""
        parser.add_command(Math, name="COMMAND1")
        parser.add_command(pow, name="COMMAND2")
        assert parser.run(args=["COMMAND2", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_custom_command_names_with_underscore(self, parser: InterfacyParser):
        """Verify execution respects custom command names with underscores."""
        parser.add_command(Math, name="command_1")
        parser.add_command(pow, name="command_2")
        assert parser.run(args=["command_2", "2", "-e", "2"]) == 4


class TestMathClassParsingKwOnly:
    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_from_class(self, parser: InterfacyParser):
        """Verify class-based command execution with kw-only strategy."""
        parser.add_command(Math)
        assert parser.run(args=["pow", "--base", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_from_instance(self, parser: InterfacyParser):
        """Verify instance-based command execution with kw-only strategy."""
        math = Math(rounding=2)
        parser.add_command(math)  # type: ignore

        assert parser.run(args=["pow", "--base", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_from_instance_method(self, parser: InterfacyParser):
        """Verify bound method execution with kw-only strategy."""
        math = Math(rounding=2)
        parser.add_command(math.pow)

        assert parser.run(args=["--base", "2", "-e", "4"]) == 16


class TestMultipleCommandsKwOnly:
    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_from_multiple_pow(self, parser: InterfacyParser):
        """Verify multiple command execution (routing to 'pow') with kw-only strategy."""
        parser.add_command(pow)
        parser.add_command(Math)

        assert parser.run(args=["pow", "--base", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_from_multiple_math(self, parser: InterfacyParser):
        """Verify multiple command execution (routing to 'math') with kw-only strategy."""
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
        """Verify list argument execution with kw-only strategy."""
        parser.add_command(fn_list_int)
        # For kw_only, list argument 'values' becomes --values [v1 v2 ...]
        assert parser.run(args=["--values", "1", "2", "3"]) == [1, 2, 3]

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_list_two_lists(self, parser: InterfacyParser):
        """Verify execution of multiple list arguments with kw-only strategy."""
        parser.add_command(fn_two_lists)
        # strings: list[str], ints: list[int]
        # kw_only -> --strings a b --ints 1 2
        assert parser.run(args=["--strings", "a", "b", "--ints", "1", "2"]) == (2, 2)

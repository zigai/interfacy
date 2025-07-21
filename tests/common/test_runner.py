import pytest

from interfacy.core import InterfacyParserCore
from tests.conftest import (
    Color,
    Math,
    function_bool_default_false,
    function_bool_default_true,
    function_bool_required,
    function_enum_arg,
    function_list_int,
    function_two_lists,
    pow,
)


class TestPowFunctionParsing:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_default_exponent(self, parser: InterfacyParserCore):
        parser.add_command(pow)
        assert parser.run(args=["2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_positional(self, parser: InterfacyParserCore):
        parser.add_command(pow)
        assert parser.run(args=["2", "-e", "4"]) == 16

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_kw_only_abbrev(self, parser: InterfacyParserCore):
        parser.add_command(pow)
        assert parser.run(args=["-b", "2", "-e", "4"]) == 16

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_kw_only_no_abbrev(self, parser: InterfacyParserCore):
        parser.add_command(pow)
        assert parser.run(args=["-base", "2", "-exponent", "4"]) == 16


class TestMathClassParsing:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_from_class(self, parser: InterfacyParserCore):
        parser.add_command(Math)
        assert parser.run(args=["pow", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_from_instance(self, parser: InterfacyParserCore):
        math = Math(rounding=2)
        parser.add_command(math)  # type: ignore

        assert parser.run(args=["pow", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_from_instance_method(self, parser: InterfacyParserCore):
        math = Math(rounding=2)
        parser.add_command(math.pow)

        assert parser.run(args=["2", "-e", "4"]) == 16


class TestMultipleCommands:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_from_multiple_pow(self, parser: InterfacyParserCore):
        parser.add_command(pow)
        parser.add_command(Math)

        assert parser.run(args=["pow", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_from_multiple_math(self, parser: InterfacyParserCore):
        parser.add_command(pow)
        parser.add_command(Math)

        assert parser.run(args=["math", "pow", "2", "-e", "2"]) == 4


class TestBooleanFlags:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_bool_required(self, parser: InterfacyParserCore):
        parser.add_command(function_bool_required)
        assert parser.run(args=["--value"]) == True
        assert parser.run(args=["--no-value"]) == False

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_bool_default_true(self, parser: InterfacyParserCore):
        parser.add_command(function_bool_default_true)

        assert parser.run(args=[]) == True
        assert parser.run(args=["--value"]) == True
        assert parser.run(args=["--no-value"]) == False

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_bool_false_by_default(self, parser: InterfacyParserCore):
        parser.add_command(function_bool_default_false)

        assert parser.run(args=[]) == False
        assert parser.run(args=["--value"]) == True
        assert parser.run(args=["--no-value"]) == False


class TestEnums:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_enum_positional(self, parser: InterfacyParserCore):
        parser.add_command(function_enum_arg)
        assert parser.run(args=["RED"]) == Color.RED

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_enum_kwarg(self, parser: InterfacyParserCore):
        parser.add_command(function_enum_arg)
        assert parser.run(args=["-c", "RED"]) == Color.RED


class TestLiterals: ...


class TestListNargs:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_list_nargs(self, parser: InterfacyParserCore):
        parser.add_command(function_list_int)
        assert parser.run(args=["1", "2", "3"]) == [1, 2, 3]

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_list_two_positional(self, parser: InterfacyParserCore):
        parser.add_command(function_two_lists)
        assert parser.run(args=["a", "b", "--ints", "1", "2"]) == (2, 2)


class TestCustomCommandNames:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_custom_command_names(self, parser: InterfacyParserCore):
        parser.add_command(Math, name="CMD_A")
        parser.add_command(pow, name="CMD_B")
        with pytest.raises(SystemExit):
            parser.run(args=["pow", "2", "-e", "2"])

        assert parser.run(args=["CMD_B", "2", "-e", "2"]) == 4

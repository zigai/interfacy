import pytest

from interfacy.core import InterfacyParser
from tests.conftest import (
    Color,
    Math,
    function_bool_default_false,
    function_bool_default_true,
    function_bool_required,
    function_enum_arg,
    function_list_int,
    function_literal_arg,
    function_two_lists,
    pow,
)


class TestPowFunctionParsing:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_default_exponent(self, parser: InterfacyParser):
        parser.add_command(pow)
        args = parser.parse_args(["2"])
        assert args == {"base": 2, "exponent": 2}

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_positional(self, parser: InterfacyParser):
        parser.add_command(pow)
        args = parser.parse_args(["2", "-e", "4"])
        assert args == {"base": 2, "exponent": 4}

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_kw_only_abbrev(self, parser: InterfacyParser):
        parser.add_command(pow)
        args = parser.parse_args(["-b", "2", "-e", "4"])
        assert args == {"base": 2, "exponent": 4}

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_kw_only_no_abbrev(self, parser: InterfacyParser):
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
        math = Math(rounding=2)
        parser.add_command(math.pow)

        args = parser.parse_args(["2", "-e", "4"])
        assert args == {"base": 2, "exponent": 4}


class TestMultipleCommands:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_from_multiple(self, parser: InterfacyParser):
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
        parser.add_command(function_bool_required)
        args = parser.parse_args(["--value"])
        assert args["value"] == True

        args = parser.parse_args(["--no-value"])
        assert args["value"] == False

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_bool_default_true(self, parser: InterfacyParser):
        parser.add_command(function_bool_default_true)
        args = parser.parse_args([])
        assert args["value"] == True

        args = parser.parse_args(["--value"])
        assert args["value"] == True

        args = parser.parse_args(["--no-value"])
        assert args["value"] == False

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_bool_false_by_default(self, parser: InterfacyParser):
        parser.add_command(function_bool_default_false)

        args = parser.parse_args([])
        assert args["value"] == False

        args = parser.parse_args(["--value"])
        assert args["value"] == True

        args = parser.parse_args(["--no-value"])
        assert args["value"] == False


class TestEnums:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_enum_positional(self, parser: InterfacyParser):
        parser.add_command(function_enum_arg)
        args = parser.parse_args(["RED"])
        assert args["color"] == Color.RED

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_enum_kwarg(self, parser: InterfacyParser):
        parser.add_command(function_enum_arg)
        args = parser.parse_args(["-c", "RED"])
        assert args["color"] == Color.RED


class TestLiterals:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_literal_positional(self, parser: InterfacyParser):
        parser.add_command(function_literal_arg)
        args = parser.parse_args(["RED"])
        assert args["color"] == "RED"

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_literal_kwarg(self, parser: InterfacyParser):
        parser.add_command(function_literal_arg)
        args = parser.parse_args(["-c", "RED"])
        assert args["color"] == "RED"


class TestListNargs:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_list_nargs(self, parser: InterfacyParser):
        parser.add_command(function_list_int)
        namespace = parser.parse_args(["1", "2", "3"])
        assert namespace["values"] == [1, 2, 3]

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_list_two_positional(self, parser: InterfacyParser):
        parser.add_command(function_two_lists)
        namespace = parser.parse_args(["a", "b", "--ints", "1", "2"])
        assert namespace["strings"] == ["a", "b"]
        assert namespace["ints"] == [1, 2]

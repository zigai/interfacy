import pytest

from interfacy.core import InterfacyParser
from tests.conftest import (
    fn_bool_default_false,
    fn_bool_default_true,
    fn_bool_required,
    fn_float_required,
    fn_str_optional,
    fn_str_required,
)


class TestPrimitives:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_str_required(self, parser: InterfacyParser):
        """Verify that a required string argument is correctly parsed from positional or flag input."""
        parser.add_command(fn_str_required)

        match parser.flag_strategy.style:
            case "required_positional":
                args = ["hello"]
            case "keyword_only":
                args = ["--name", "hello"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

        assert parser.run(args=args) == "hello"

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_str_optional(self, parser: InterfacyParser):
        """Verify that an optional string argument defaults correctly and accepts flag input."""
        parser.add_command(fn_str_optional)
        assert parser.run(args=[]) == "default"
        assert parser.run(args=["--name", "custom"]) == "custom"

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_float_required(self, parser: InterfacyParser):
        """Verify that a required float argument is parsed and typed correctly."""
        parser.add_command(fn_float_required)

        match parser.flag_strategy.style:
            case "required_positional":
                args = ["3.14"]
            case "keyword_only":
                args = ["--value", "3.14"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

        assert parser.run(args=args) == 3.14

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_bool_required(self, parser: InterfacyParser):
        """Verify that a required boolean argument parses --flag and --no-flag correctly."""
        parser.add_command(fn_bool_required)
        assert parser.run(args=["--value"]) is True
        assert parser.run(args=["--no-value"]) is False

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_bool_default_true(self, parser: InterfacyParser):
        """Verify that a boolean defaulting to True handles empty input and --no-flag."""
        parser.add_command(fn_bool_default_true)
        assert parser.run(args=[]) is True
        assert parser.run(args=["--no-value"]) is False

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_bool_default_false(self, parser: InterfacyParser):
        """Verify that a boolean defaulting to False handles empty input and --flag."""
        parser.add_command(fn_bool_default_false)
        assert parser.run(args=[]) is False
        assert parser.run(args=["--value"]) is True

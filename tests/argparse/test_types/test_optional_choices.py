import pytest

from interfacy.core import InterfacyParser
from tests.conftest import Color, fn_enum_arg, fn_enum_optional, fn_literal_arg, fn_literal_optional


class TestOptionalChoices:
    """Tests for Enzyme and Literal types, both required and optional."""

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_enum_required(self, parser: InterfacyParser):
        """Verify required Enum matches by name."""
        parser.add_command(fn_enum_arg)
        match parser.flag_strategy.style:
            case "required_positional":
                args = ["RED"]
            case "keyword_only":
                args = ["--color", "RED"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")
        assert parser.run(args=args) == Color.RED

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_enum_optional_provided(self, parser: InterfacyParser):
        """Verify optional Enum matches when provided."""
        parser.add_command(fn_enum_optional)
        args = ["--color", "GREEN"]
        assert parser.run(args=args) == Color.GREEN

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_enum_optional_default(self, parser: InterfacyParser):
        """Verify optional Enum returns None when omitted."""
        parser.add_command(fn_enum_optional)
        result = parser.run(args=[])
        assert result is None

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_literal_required(self, parser: InterfacyParser):
        """Verify required Literal matches specific string values."""
        parser.add_command(fn_literal_arg)
        match parser.flag_strategy.style:
            case "required_positional":
                args = ["BLUE"]
            case "keyword_only":
                args = ["--color", "BLUE"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

        assert parser.run(args=args) == "BLUE"

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_literal_optional_provided(self, parser: InterfacyParser):
        """Verify optional Literal matches when provided."""
        parser.add_command(fn_literal_optional)
        args = ["--color", "RED"]
        assert parser.run(args=args) == "RED"

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_literal_optional_default(self, parser: InterfacyParser):
        """Verify optional Literal returns None when omitted."""
        parser.add_command(fn_literal_optional)
        result = parser.run(args=[])
        assert result is None

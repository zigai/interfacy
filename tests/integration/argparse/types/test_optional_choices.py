import pytest

from interfacy import Interfacy
from tests.fixtures.commands import (
    fn_enum_arg,
    fn_enum_optional,
    fn_literal_arg,
    fn_literal_optional,
)
from tests.fixtures.models import Color


class TestOptionalChoices:
    """Tests for Enzyme and Literal types, both required and optional."""

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_enum_required(self, parser: Interfacy):
        """Verify required Enum matches by name."""
        parser.add_command(fn_enum_arg)
        match parser.metadata["flag_style"]:
            case "required_positional":
                args = ["RED"]
            case "keyword_only":
                args = ["--color", "RED"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.metadata['flag_style']}")
        assert parser.invoke(args=args) == Color.RED

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_enum_optional_provided(self, parser: Interfacy):
        """Verify optional Enum matches when provided."""
        parser.add_command(fn_enum_optional)
        args = ["--color", "GREEN"]
        assert parser.invoke(args=args) == Color.GREEN

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_enum_optional_default(self, parser: Interfacy):
        """Verify optional Enum returns None when omitted."""
        parser.add_command(fn_enum_optional)
        result = parser.invoke(args=[])
        assert result is None

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_literal_required(self, parser: Interfacy):
        """Verify required Literal matches specific string values."""
        parser.add_command(fn_literal_arg)
        match parser.metadata["flag_style"]:
            case "required_positional":
                args = ["BLUE"]
            case "keyword_only":
                args = ["--color", "BLUE"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.metadata['flag_style']}")

        assert parser.invoke(args=args) == "BLUE"

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_literal_optional_provided(self, parser: Interfacy):
        """Verify optional Literal matches when provided."""
        parser.add_command(fn_literal_optional)
        args = ["--color", "RED"]
        assert parser.invoke(args=args) == "RED"

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_literal_optional_default(self, parser: Interfacy):
        """Verify optional Literal returns None when omitted."""
        parser.add_command(fn_literal_optional)
        result = parser.invoke(args=[])
        assert result is None

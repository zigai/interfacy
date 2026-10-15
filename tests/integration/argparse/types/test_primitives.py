from __future__ import annotations

from typing import Any

import pytest

from interfacy import Interfacy
from interfacy.exceptions import UsageError
from tests.fixtures.commands import (
    fn_str_optional,
)


class TestPrimitives:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_bad_int_error_uses_user_facing_type_name(self, parser: Interfacy):
        """Invalid typed values identify the option and expected input without echoing it."""

        def greet(name: str, times: int = 1) -> str:
            return name * times

        parser.add_command(greet)

        with pytest.raises(UsageError) as excinfo:
            parser.parse_args(["Ada", "--times", "bad"])

        assert str(excinfo.value) == "'--times' requires an integer"
        assert excinfo.value.diagnostic.argument == "--times"
        assert "bad" not in str(excinfo.value)

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_str_required(self, parser: Interfacy):
        """Verify that a required string argument is correctly parsed from positional or flag input."""

        def fn_str_required(name: str) -> str:
            return name

        parser.add_command(fn_str_required)

        match parser.metadata["flag_style"]:
            case "required_positional":
                args = ["hello"]
            case "keyword_only":
                args = ["--name", "hello"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.metadata['flag_style']}")

        assert parser.invoke(args=args) == "hello"

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_str_optional(self, parser: Interfacy):
        """Verify that an optional string argument defaults correctly and accepts flag input."""
        parser.add_command(fn_str_optional)
        assert parser.invoke(args=[]) == "default"
        assert parser.invoke(args=["--name", "custom"]) == "custom"

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_float_required(self, parser: Interfacy):
        """Verify that a required float argument is parsed and typed correctly."""

        def fn_float_required(value: float) -> float:
            return value

        parser.add_command(fn_float_required)

        match parser.metadata["flag_style"]:
            case "required_positional":
                args = ["3.14"]
            case "keyword_only":
                args = ["--value", "3.14"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.metadata['flag_style']}")

        assert parser.invoke(args=args) == 3.14

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_single_letter_bool_default_true_accepts_negative_long_flag(self, parser: Interfacy):
        """Single-letter booleans defaulting to True should accept a --no-x form."""

        def short_toggle(x: bool = True) -> bool:
            return x

        parser.add_command(short_toggle)

        assert parser.invoke(args=[]) is True
        assert parser.invoke(args=["--no-x"]) is False


def test_any_and_object_parameters() -> None:
    """Verify that parameters typed as Any or object accept CLI input without error."""

    def echo(x: Any, y: object) -> dict[str, Any]:
        return {"x": x, "y": y}

    cli = Interfacy()
    cli.add_command(echo)
    res = cli.invoke(args=["hello", "world"])
    assert res == {"x": "hello", "y": "world"}

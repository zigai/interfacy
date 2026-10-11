import pytest

from interfacy import Interfacy
from tests.fixtures.commands import fn_optional_int


class TestOptionals:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_optional_str(self, parser: Interfacy):
        """Verify that Optional[str] handles default None and provided string flag."""

        def fn_optional_str(value: str | None = None) -> str | None:
            return value

        parser.add_command(fn_optional_str)
        assert parser.invoke(args=[]) is None
        assert parser.invoke(args=["--value", "foo"]) == "foo"

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_optional_int(self, parser: Interfacy):
        """Verify that Optional[int] handles default None and provided integer flag."""
        parser.add_command(fn_optional_int)
        assert parser.invoke(args=[]) is None
        assert parser.invoke(args=["--value", "42"]) == 42

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_mixed_optional(self, parser: Interfacy):
        """Verify that mixed required and optional arguments behave correctly across strategies."""

        def fn_mixed_optional(
            required: str,
            optional_int: int | None = None,
            optional_str: str = "default",
        ) -> dict[str, object]:
            return {
                "required": required,
                "optional_int": optional_int,
                "optional_str": optional_str,
            }

        parser.add_command(fn_mixed_optional)

        match parser.metadata["flag_style"]:
            case "required_positional":
                assert parser.invoke(args=["A"]) == {
                    "required": "A",
                    "optional_int": None,
                    "optional_str": "default",
                }
                assert parser.invoke(args=["A", "--optional-int", "10"]) == {
                    "required": "A",
                    "optional_int": 10,
                    "optional_str": "default",
                }
            case "keyword_only":
                assert parser.invoke(args=["--required", "A"]) == {
                    "required": "A",
                    "optional_int": None,
                    "optional_str": "default",
                }
                assert parser.invoke(args=["--required", "A", "--optional-int", "10"]) == {
                    "required": "A",
                    "optional_int": 10,
                    "optional_str": "default",
                }
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.metadata['flag_style']}")

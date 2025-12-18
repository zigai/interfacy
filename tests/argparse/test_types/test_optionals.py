import pytest

from interfacy.core import InterfacyParser
from tests.conftest import fn_mixed_optional, fn_optional_int, fn_optional_str


class TestOptionals:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_optional_str(self, parser: InterfacyParser):
        """Verify that Optional[str] handles default None and provided string flag."""
        parser.add_command(fn_optional_str)
        assert parser.run(args=[]) is None
        assert parser.run(args=["--value", "foo"]) == "foo"

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_optional_int(self, parser: InterfacyParser):
        """Verify that Optional[int] handles default None and provided integer flag."""
        parser.add_command(fn_optional_int)
        assert parser.run(args=[]) is None
        assert parser.run(args=["--value", "42"]) == 42

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_mixed_optional(self, parser: InterfacyParser):
        """Verify that mixed required and optional arguments behave correctly across strategies."""
        parser.add_command(fn_mixed_optional)

        match parser.flag_strategy.style:
            case "required_positional":
                assert parser.run(args=["A"]) == {
                    "required": "A",
                    "optional_int": None,
                    "optional_str": "default",
                }
                assert parser.run(args=["A", "--optional-int", "10"]) == {
                    "required": "A",
                    "optional_int": 10,
                    "optional_str": "default",
                }
            case "keyword_only":
                assert parser.run(args=["--required", "A"]) == {
                    "required": "A",
                    "optional_int": None,
                    "optional_str": "default",
                }
                assert parser.run(args=["--required", "A", "--optional-int", "10"]) == {
                    "required": "A",
                    "optional_int": 10,
                    "optional_str": "default",
                }
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

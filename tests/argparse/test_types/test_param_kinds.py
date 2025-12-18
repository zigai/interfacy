import pytest

from interfacy.core import InterfacyParser
from tests.conftest import fn_all_zones, fn_keyword_only, fn_positional_only, fn_varargs


class TestParamKinds:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_positional_only(self, parser: InterfacyParser):
        """Verify positional-only arguments (slash syntax) in supported strategies."""
        parser.add_command(fn_positional_only)  # func(a, b, /)

        match parser.flag_strategy.style:
            case "required_positional":
                args = ["1", "2"]
            case "keyword_only":
                args = ["-a", "1", "-b", "2"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

        assert parser.run(args=args) == 3

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_keyword_only(self, parser: InterfacyParser):
        """Verify keyword-only arguments (star syntax) in supported strategies."""
        parser.add_command(fn_keyword_only)  # func(*, a, b)

        match parser.flag_strategy.style:
            case "required_positional":
                args = ["1", "2"]
            case "keyword_only":
                args = ["-a", "1", "-b", "2"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

        assert parser.run(args=args) == 3

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_varargs(self, parser: InterfacyParser):
        """Verify *args support (variable positional arguments)."""
        parser.add_command(fn_varargs)  # func(*args)

        match parser.flag_strategy.style:
            case "required_positional":
                args = ["1", "2", "3"]
            case "keyword_only":
                args = ["--args", "1", "2", "3"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

        assert parser.run(args=args) == 6

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_all_zones(self, parser: InterfacyParser):
        """Verify mixed parameter kinds (pos-only, standard, kw-only) in one signature."""
        parser.add_command(fn_all_zones)

        match parser.flag_strategy.style:
            case "required_positional":
                args = ["1", "2", "3"]
            case "keyword_only":
                args = ["-a", "1", "-b", "2", "-c", "3"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

        assert parser.run(args=args) == 6

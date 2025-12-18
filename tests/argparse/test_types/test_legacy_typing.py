import pytest

from interfacy.core import InterfacyParser
from tests.conftest import fn_legacy_dict, fn_legacy_list, fn_legacy_optional, fn_legacy_union


class TestLegacyTyping:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_legacy_list(self, parser: InterfacyParser):
        """Verify that typing.List is supported identically to built-in list."""
        parser.add_command(fn_legacy_list)
        match parser.flag_strategy.style:
            case "required_positional":
                args = ["1", "2"]
            case "keyword_only":
                args = ["-x", "1", "2"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")
        assert parser.run(args=args) == [1, 2]

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_legacy_dict(self, parser: InterfacyParser):
        """Verify that typing.Dict is supported identically to built-in dict."""
        parser.add_command(fn_legacy_dict)
        import json

        data = {"a": 1}
        val = json.dumps(data)

        match parser.flag_strategy.style:
            case "required_positional":
                args = [val]
            case "keyword_only":
                args = ["-x", val]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

        assert parser.run(args=args) == data

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_legacy_optional(self, parser: InterfacyParser):
        """Verify that typing.Optional is supported identically to built-in Optional."""
        parser.add_command(fn_legacy_optional)
        assert parser.run(args=[]) is None
        assert parser.run(args=["-x", "42"]) == 42

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_legacy_union(self, parser: InterfacyParser):
        """Verify that typing.Union[int, str] parses as int if possible, else str."""
        parser.add_command(fn_legacy_union)

        match parser.flag_strategy.style:
            case "required_positional":
                args_int = ["1"]
                args_str = ["a"]
            case "keyword_only":
                args_int = ["-x", "1"]
                args_str = ["-x", "a"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

        assert parser.run(args=args_int) == 1
        assert parser.run(args=args_str) == "a"

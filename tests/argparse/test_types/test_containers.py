from typing import Dict, List, Tuple

import pytest

from interfacy.core import InterfacyParser
from tests.conftest import (
    fn_legacy_list,
    fn_list_int,
    fn_list_int_optional,
    fn_list_str,
    fn_list_str_optional,
)


def fn_tuple_strs(items: tuple[str, str]):
    return items


def fn_tuple_int_str(items: tuple[int, str]):
    """Heterogeneous tuple: first element should be int, second should be str."""
    return items


def fn_dict_str_int(data: dict[str, int]):
    return data


class TestContainers:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_list_int(self, parser: InterfacyParser):
        """Verify that a list of integers accumulates values from multiple arguments."""
        parser.add_command(fn_list_int)
        match parser.flag_strategy.style:
            case "required_positional":
                args = ["1", "2", "3"]
            case "keyword_only":
                args = ["--values", "1", "2", "3"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

        assert parser.run(args=args) == [1, 2, 3]

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_list_str(self, parser: InterfacyParser):
        """Verify that a list of strings parses correctly."""
        parser.add_command(fn_list_str)

        match parser.flag_strategy.style:
            case "required_positional":
                args = ["alpha", "beta", "gamma"]
            case "keyword_only":
                args = ["--items", "alpha", "beta", "gamma"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

        assert parser.run(args=args) == ["alpha", "beta", "gamma"]

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_list_str_optional_with_values(self, parser: InterfacyParser):
        """Verify optional union list parses provided values."""
        parser.add_command(fn_list_str_optional)
        args = ["--items", "foo", "bar"]
        assert parser.run(args=args) == ["foo", "bar"]

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_list_str_optional_default_none(self, parser: InterfacyParser):
        """Verify optional union list returns None when not provided."""
        parser.add_command(fn_list_str_optional)
        result = parser.run(args=[])
        assert result is None

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_list_int_optional_with_values(self, parser: InterfacyParser):
        """Verify optional union list[int] parses provided values."""
        parser.add_command(fn_list_int_optional)
        args = ["--values", "10", "20", "30"]
        assert parser.run(args=args) == [10, 20, 30]

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_tuple_strs(self, parser: InterfacyParser):
        """Verify that a tuple of strings is correctly parsed (expecting fixed arguments)."""
        parser.add_command(fn_tuple_strs, name="fn-tuple")

        match parser.flag_strategy.style:
            case "required_positional":
                args = ["a", "b"]
            case "keyword_only":
                args = ["--items", "a", "b"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

        assert parser.run(args=args) == ("a", "b")

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_tuple_mixed_types(self, parser: InterfacyParser):
        """Verify that a heterogeneous tuple converts each element to its annotated type."""
        parser.add_command(fn_tuple_int_str, name="fn-tuple-mixed")

        match parser.flag_strategy.style:
            case "required_positional":
                args = ["123", "hello"]
            case "keyword_only":
                args = ["--items", "123", "hello"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

        result = parser.run(args=args)
        # Expected: (123, "hello") - int and str
        # Actual bug: ("123", "hello") - both strings, int conversion not applied
        assert result == (123, "hello")
        assert isinstance(result[0], int), f"First element should be int, got {type(result[0])}"
        assert isinstance(result[1], str), f"Second element should be str, got {type(result[1])}"

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_dict_str_int(self, parser: InterfacyParser):
        """Verify that a dictionary is parsed from a JSON string."""
        parser.add_command(fn_dict_str_int, name="fn-dict")
        import json

        data = {"a": 1, "b": 2}
        json_str = json.dumps(data)

        match parser.flag_strategy.style:
            case "required_positional":
                args = [json_str]
            case "keyword_only":
                args = ["--data", json_str]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

        result = parser.run(args=args)
        assert result == data

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_legacy_list(self, parser: InterfacyParser):
        """Verify that a legacy typing.List is handled identically to built-in list."""
        parser.add_command(fn_legacy_list)
        match parser.flag_strategy.style:
            case "required_positional":
                args = ["10", "20"]
            case "keyword_only":
                args = ["-x", "10", "20"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

        assert parser.run(args=args) == [10, 20]

from dataclasses import dataclass

import pytest

from interfacy import Interfacy
from interfacy.exceptions import UsageError
from tests.fixtures.commands import (
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


@dataclass
class User:
    name: str
    age: int


def fn_list_tuple_int_str(items: list[tuple[int, str]]):
    return items


def fn_tuple_users(pair: tuple[User, User]):
    return pair


def fn_list_users(users: list[User]):
    return users


def fn_dict_str_int(data: dict[str, int]):
    return data


class TestContainers:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_list_int(self, parser: Interfacy):
        """Verify that a list of integers accumulates values from multiple arguments."""
        parser.add_command(fn_list_int)
        match parser.metadata["flag_style"]:
            case "required_positional":
                args = ["1", "2", "3"]
            case "keyword_only":
                args = ["--values", "1", "2", "3"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.metadata['flag_style']}")

        assert parser.invoke(args=args) == [1, 2, 3]

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_list_str(self, parser: Interfacy):
        """Verify that a list of strings parses correctly."""
        parser.add_command(fn_list_str)

        match parser.metadata["flag_style"]:
            case "required_positional":
                args = ["alpha", "beta", "gamma"]
            case "keyword_only":
                args = ["--items", "alpha", "beta", "gamma"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.metadata['flag_style']}")

        assert parser.invoke(args=args) == ["alpha", "beta", "gamma"]

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_required_list_positional_rejects_empty_input(self, parser: Interfacy):
        """Required list positionals should fail when no values are provided."""
        parser.add_command(fn_list_str)

        with pytest.raises(UsageError):
            parser.parse_args([])

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_required_list_option_rejects_flag_without_values(self, parser: Interfacy):
        """Required list options should fail when the flag is present without any values."""
        parser.add_command(fn_list_str)

        with pytest.raises(UsageError):
            parser.parse_args(["--items"])

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_list_str_optional_with_values(self, parser: Interfacy):
        """Verify optional union list parses provided values."""
        parser.add_command(fn_list_str_optional)
        args = ["--items", "foo", "bar"]
        assert parser.invoke(args=args) == ["foo", "bar"]

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_list_str_optional_default_none(self, parser: Interfacy):
        """Verify optional union list returns None when not provided."""
        parser.add_command(fn_list_str_optional)
        result = parser.invoke(args=[])
        assert result is None

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_list_int_optional_with_values(self, parser: Interfacy):
        """Verify optional union list[int] parses provided values."""
        parser.add_command(fn_list_int_optional)
        args = ["--values", "10", "20", "30"]
        assert parser.invoke(args=args) == [10, 20, 30]

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_tuple_strs(self, parser: Interfacy):
        """Verify that a tuple of strings is correctly parsed (expecting fixed arguments)."""
        parser.add_command(fn_tuple_strs, name="fn-tuple")

        match parser.metadata["flag_style"]:
            case "required_positional":
                args = ["a", "b"]
            case "keyword_only":
                args = ["--items", "a", "b"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.metadata['flag_style']}")

        assert parser.invoke(args=args) == ("a", "b")

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_tuple_mixed_types(self, parser: Interfacy):
        """Verify that a heterogeneous tuple converts each element to its annotated type."""
        parser.add_command(fn_tuple_int_str, name="fn-tuple-mixed")

        match parser.metadata["flag_style"]:
            case "required_positional":
                args = ["123", "hello"]
            case "keyword_only":
                args = ["--items", "123", "hello"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.metadata['flag_style']}")

        result = parser.invoke(args=args)
        # Expected: (123, "hello") - int and str
        # Actual bug: ("123", "hello") - both strings, int conversion not applied
        assert result == (123, "hello")
        assert isinstance(result[0], int), f"First element should be int, got {type(result[0])}"
        assert isinstance(result[1], str), f"Second element should be str, got {type(result[1])}"

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_list_of_fixed_tuples(self, parser: Interfacy):
        """Verify repeated fixed-size tuple items are grouped from flat CLI values."""
        parser.add_command(fn_list_tuple_int_str, name="fn-list-tuples")

        match parser.metadata["flag_style"]:
            case "required_positional":
                args = ["1", "a", "2", "b"]
            case "keyword_only":
                args = ["--items", "1", "a", "2", "b"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.metadata['flag_style']}")

        assert parser.invoke(args=args) == [(1, "a"), (2, "b")]

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_list_of_fixed_tuples_rejects_incomplete_group(self, parser: Interfacy):
        """Verify grouped repeated tuple values fail when the final group is incomplete."""
        parser.add_command(fn_list_tuple_int_str, name="fn-list-tuples")

        match parser.metadata["flag_style"]:
            case "required_positional":
                args = ["1", "a", "2"]
            case "keyword_only":
                args = ["--items", "1", "a", "2"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.metadata['flag_style']}")

        with pytest.raises(UsageError):
            parser.parse_args(args)

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_tuple_of_dataclasses_from_flat_values(self, parser: Interfacy):
        """Verify fixed tuples can contain fixed-size dataclass values."""
        parser.add_command(fn_tuple_users, name="fn-user-pair")

        match parser.metadata["flag_style"]:
            case "required_positional":
                args = ["ann", "1", "bob", "2"]
            case "keyword_only":
                args = ["--pair", "ann", "1", "bob", "2"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.metadata['flag_style']}")

        assert parser.invoke(args=args) == (User("ann", 1), User("bob", 2))

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_list_of_dataclasses_from_flat_values(self, parser: Interfacy):
        """Verify repeated dataclass items are grouped from flat CLI values."""
        parser.add_command(fn_list_users, name="fn-users")

        match parser.metadata["flag_style"]:
            case "required_positional":
                args = ["ann", "1", "bob", "2"]
            case "keyword_only":
                args = ["--users", "ann", "1", "bob", "2"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.metadata['flag_style']}")

        assert parser.invoke(args=args) == [User("ann", 1), User("bob", 2)]

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_dict_str_int(self, parser: Interfacy):
        """Verify that a dictionary is parsed from a JSON string."""
        parser.add_command(fn_dict_str_int, name="fn-dict")
        import json

        data = {"a": 1, "b": 2}
        json_str = json.dumps(data)

        match parser.metadata["flag_style"]:
            case "required_positional":
                args = [json_str]
            case "keyword_only":
                args = ["--data", json_str]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.metadata['flag_style']}")

        result = parser.invoke(args=args)
        assert result == data

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_legacy_list(self, parser: Interfacy):
        """Verify that a legacy typing.List is handled identically to built-in list."""
        parser.add_command(fn_legacy_list)
        match parser.metadata["flag_style"]:
            case "required_positional":
                args = ["10", "20"]
            case "keyword_only":
                args = ["-x", "10", "20"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.metadata['flag_style']}")

        assert parser.invoke(args=args) == [10, 20]

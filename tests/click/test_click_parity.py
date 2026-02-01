from __future__ import annotations

from dataclasses import dataclass

import pytest

from interfacy.group import CommandGroup
from tests.conftest import (
    Math,
    fn_bool_default_false,
    fn_bool_default_true,
    fn_list_int,
    fn_list_int_optional,
)


def fn_tuple_mixed(values: tuple[int, str, float]) -> tuple[int, str, float]:
    return values


def fn_echo(msg: str) -> str:
    return msg


def fn_echo_cli(msg: str) -> str:
    return msg


@dataclass
class User:
    name: str
    age: int


def fn_user(user: User) -> User:
    return user


class TestClickListOptions:
    @pytest.mark.parametrize("parser", ["click_kw_only"], indirect=True)
    def test_list_option_values(self, parser):
        parser.add_command(fn_list_int)
        assert parser.run(args=["--values", "1", "2", "3"]) == [1, 2, 3]

    @pytest.mark.parametrize("parser", ["click_kw_only"], indirect=True)
    def test_list_option_negatives(self, parser):
        parser.add_command(fn_list_int)
        assert parser.run(args=["--values", "-1", "-2"]) == [-1, -2]


class TestClickBooleanFlags:
    @pytest.mark.parametrize("parser", ["click_kw_only"], indirect=True)
    def test_bool_default_true(self, parser):
        parser.add_command(fn_bool_default_true)
        assert parser.run(args=[]) is True
        assert parser.run(args=["--no-value"]) is False

    @pytest.mark.parametrize("parser", ["click_kw_only"], indirect=True)
    def test_bool_default_false(self, parser):
        parser.add_command(fn_bool_default_false)
        assert parser.run(args=[]) is False
        assert parser.run(args=["--value"]) is True


class TestClickTupleParsing:
    @pytest.mark.parametrize("parser", ["click_req_pos"], indirect=True)
    def test_tuple_mixed(self, parser):
        parser.add_command(fn_tuple_mixed)
        assert parser.run(args=["1", "hello", "2.5"]) == (1, "hello", 2.5)


class TestClickOptionalUnionList:
    @pytest.mark.parametrize("parser", ["click_kw_only"], indirect=True)
    def test_optional_union_list_default(self, parser):
        parser.add_command(fn_list_int_optional)
        assert parser.run(args=[]) is None
        assert parser.run(args=["--values", "1", "2"]) == [1, 2]


class TestClickAliases:
    @pytest.mark.parametrize("parser", ["click_req_pos"], indirect=True)
    def test_alias_invocation(self, parser):
        def primary(x: int) -> int:
            return x

        def secondary(x: int) -> int:
            return x + 1

        parser.add_command(primary, aliases=["alias"])
        parser.add_command(secondary)

        assert parser.run(args=["alias", "3"]) == 3


class TestClickClassCommands:
    @pytest.mark.parametrize("parser", ["click_req_pos"], indirect=True)
    def test_class_with_initializer(self, parser):
        parser.add_command(Math)
        assert parser.run(args=["pow", "2", "-e", "2"]) == 4
        assert parser.run(args=["--rounding", "2", "pow", "2", "-e", "2"]) == 4


class TestClickNestedGroups:
    @pytest.mark.parametrize("parser", ["click_req_pos"], indirect=True)
    def test_nested_group_namespace(self, parser):
        def greet(name: str) -> str:
            return f"Hello {name}"

        root = CommandGroup("root")
        sub = CommandGroup("sub")
        sub.add_command(greet)
        root.add_group(sub)

        parser.add_command(root)
        namespace = parser.parse_args(["root", "sub", "greet", "Ada"])
        assert namespace == {
            "command": "root",
            "root": {
                "command": "sub",
                "sub": {
                    "command_1": "greet",
                    "greet": {"name": "Ada"},
                },
            },
        }


class TestClickPipes:
    @pytest.mark.parametrize("parser", ["click_req_pos"], indirect=True)
    def test_pipe_single_target(self, parser, mocker):
        parser.add_command(fn_echo, pipe_targets="msg")
        mocker.patch("interfacy.core.read_piped", return_value="hello")
        assert parser.run(args=[]) == "hello"

    @pytest.mark.parametrize("parser", ["click_kw_only"], indirect=True)
    def test_pipe_priority(self, parser, mocker):
        parser.add_command(fn_echo_cli, pipe_targets={"bindings": "msg", "priority": "pipe"})
        mocker.patch("interfacy.core.read_piped", return_value="piped")
        assert parser.run(args=["--msg", "cli"]) == "piped"


class TestClickModelExpansion:
    @pytest.mark.parametrize("parser", ["click_kw_only"], indirect=True)
    def test_dataclass_expansion(self, parser):
        parser.add_command(fn_user)
        result = parser.run(args=["--user.name", "Alice", "--user.age", "30"])
        assert isinstance(result, User)
        assert result.name == "Alice"
        assert result.age == 30

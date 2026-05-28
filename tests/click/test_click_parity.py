from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import click
import pytest

from interfacy import ExecutableFlag
from interfacy.appearance.layouts import ArgparseLayout, StandardLayout
from interfacy.click_backend import ClickParser
from interfacy.click_backend.commands import (
    InterfacyClickArgument,
    InterfacyClickCommand,
    InterfacyClickGroup,
    InterfacyClickOption,
)
from interfacy.group import CommandGroup
from tests.conftest import (
    Math,
    fn_bool_default_false,
    fn_bool_default_true,
    fn_list_int,
    fn_list_int_optional,
)


def fn_metadata_help(
    *,
    mode: Literal["fast", "safe", "balanced"] = "balanced",
    level: int = 2,
) -> tuple[str, int]:
    return mode, level


def test_click_standard_layout_renders_schema_metadata_in_help() -> None:
    parser = ClickParser(
        help_layout=StandardLayout(),
        sys_exit_enabled=False,
        print_result=False,
    )
    parser.add_command(fn_metadata_help)
    command = parser.build_parser()
    help_text = command.get_help(click.Context(command))

    assert "-l, --level" in help_text
    assert "-m, --mode" in help_text
    assert "[default: 2]" in help_text
    assert "[default: balanced] [choices: fast, safe," in help_text
    assert "balanced]" in help_text


def test_click_argparse_layout_renders_metavars_and_schema_metadata_in_help() -> None:
    parser = ClickParser(
        help_layout=ArgparseLayout(),
        sys_exit_enabled=False,
        print_result=False,
    )
    parser.add_command(fn_metadata_help)
    command = parser.build_parser()
    help_text = command.get_help(click.Context(command))

    assert "-l, --level LEVEL" in help_text
    assert "-m, --mode MODE" in help_text
    assert "Defaults to 2." in help_text
    assert "Defaults to balanced. Choices: fast, safe," in help_text
    assert "balanced." in help_text


def fn_tuple_mixed(values: tuple[int, str, float]) -> tuple[int, str, float]:
    return values


def fn_list_tuple_int_str(values: list[tuple[int, str]]) -> list[tuple[int, str]]:
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


def fn_user_pair(pair: tuple[User, User]) -> tuple[User, User]:
    return pair


def fn_users(users: list[User]) -> list[User]:
    return users


class TestClickListOptions:
    @pytest.mark.parametrize("parser", ["click_kw_only"], indirect=True)
    def test_list_option_values(self, parser):
        parser.add_command(fn_list_int)
        assert parser.run(args=["--values", "1", "2", "3"]) == [1, 2, 3]

    @pytest.mark.parametrize("parser", ["click_kw_only"], indirect=True)
    def test_list_option_negatives(self, parser):
        parser.add_command(fn_list_int)
        assert parser.run(args=["--values", "-1", "-2"]) == [-1, -2]

    @pytest.mark.parametrize("parser", ["click_req_pos", "click_kw_only"], indirect=True)
    def test_list_of_fixed_tuples(self, parser):
        parser.add_command(fn_list_tuple_int_str)
        match parser.flag_strategy.style:
            case "required_positional":
                args = ["1", "a", "2", "b"]
            case "keyword_only":
                args = ["--values", "1", "a", "2", "b"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

        assert parser.run(args=args) == [(1, "a"), (2, "b")]

    @pytest.mark.parametrize("parser", ["click_req_pos", "click_kw_only"], indirect=True)
    def test_list_of_fixed_tuples_rejects_incomplete_group(self, parser):
        parser.add_command(fn_list_tuple_int_str)
        match parser.flag_strategy.style:
            case "required_positional":
                args = ["1", "a", "2"]
            case "keyword_only":
                args = ["--values", "1", "a", "2"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

        result = parser.run(args=args)

        assert isinstance(result, SystemExit)
        assert result.code == 2

    @pytest.mark.parametrize("parser", ["click_req_pos", "click_kw_only"], indirect=True)
    def test_tuple_of_dataclasses_from_flat_values(self, parser):
        parser.add_command(fn_user_pair)
        match parser.flag_strategy.style:
            case "required_positional":
                args = ["ann", "1", "bob", "2"]
            case "keyword_only":
                args = ["--pair", "ann", "1", "bob", "2"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

        assert parser.run(args=args) == (User("ann", 1), User("bob", 2))

    @pytest.mark.parametrize("parser", ["click_req_pos", "click_kw_only"], indirect=True)
    def test_list_of_dataclasses_from_flat_values(self, parser):
        parser.add_command(fn_users)
        match parser.flag_strategy.style:
            case "required_positional":
                args = ["ann", "1", "bob", "2"]
            case "keyword_only":
                args = ["--users", "ann", "1", "bob", "2"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

        assert parser.run(args=args) == [User("ann", 1), User("bob", 2)]


class TestClickBooleanFlags:
    @pytest.mark.parametrize("parser", ["click_kw_only"], indirect=True)
    def test_bool_default_true(self, parser):
        parser.add_command(fn_bool_default_true)
        assert parser.run(args=[]) is True
        assert parser.run(args=["--no-value"]) is False

    @pytest.mark.parametrize("parser", ["click_kw_only"], indirect=True)
    def test_bool_default_true_help_keeps_negative_flag_form(self, parser):
        parser.add_command(fn_bool_default_true)

        command = parser.build_parser()
        help_text = command.get_help(click.Context(command))

        assert "--no-value" in help_text

    @pytest.mark.parametrize("parser", ["click_kw_only"], indirect=True)
    def test_single_letter_bool_default_true_accepts_negative_long_flag(self, parser):
        def short_toggle(x: bool = True) -> bool:
            return x

        parser.add_command(short_toggle)

        assert parser.run(args=[]) is True
        assert parser.run(args=["--no-x"]) is False

    @pytest.mark.parametrize("parser", ["click_kw_only"], indirect=True)
    def test_bool_default_false(self, parser):
        parser.add_command(fn_bool_default_false)
        assert parser.run(args=[]) is False
        assert parser.run(args=["--value"]) is True

    def test_parser_help_position_keeps_long_executable_flag_help_inline(self) -> None:
        parser = ClickParser(
            help_position=42,
            executable_flags=[
                ExecutableFlag(
                    ("-d", "--disable-job-duration-limit"),
                    lambda: None,
                    help="Disable the per-job duration limit.",
                )
            ],
            sys_exit_enabled=False,
            print_result=False,
        )

        def serve() -> None:
            """Run the service."""

        parser.add_command(serve)
        command = parser.build_parser()
        help_text = command.get_help(click.Context(command))

        assert "usage:" in help_text
        assert re.search(
            r"^\s*-d, --disable-job-duration-limit\s+Disable the per-job duration limit\.$",
            help_text,
            re.MULTILINE,
        )

    def test_default_click_help_keeps_long_executable_flag_wrapped(self) -> None:
        parser = ClickParser(
            executable_flags=[
                ExecutableFlag(
                    ("-d", "--disable-job-duration-limit"),
                    lambda: None,
                    help="Disable the per-job duration limit.",
                )
            ],
            sys_exit_enabled=False,
            print_result=False,
        )

        def serve() -> None:
            """Run the service."""

        parser.add_command(serve)
        command = parser.build_parser()
        help_text = command.get_help(click.Context(command))

        assert re.search(
            r"^\s*-d, --disable-job-duration-limit\s+Disable the per-job duration limit\.$",
            help_text,
            re.MULTILINE,
        )
        assert "Disable the per-job duration limit." in help_text


def test_interfacy_click_command_help_position_aligns_positionals_and_options() -> None:
    command = InterfacyClickCommand(
        name="deploy",
        help="Deploy an application build.",
        params=[
            InterfacyClickArgument(("environment",), help="Target environment."),
            InterfacyClickOption(["region", "--region"], help="Cloud region."),
        ],
    )
    command.interfacy_help_position = 38
    command.interfacy_help_position_explicit = True

    help_text = command.get_help(click.Context(command))

    assert "Positionals:" in help_text
    assert re.search(r"^\s*environment\s+Target environment\.$", help_text, re.MULTILINE)
    assert re.search(r"^\s*--region\s+Cloud region\.$", help_text, re.MULTILINE)


def test_interfacy_click_group_help_position_aligns_command_rows() -> None:
    group = InterfacyClickGroup(name="main", help="Maintenance tools.")
    group.add_command(click.Command("status", help="Show current status."))
    group.add_command(
        click.Command(
            "disable-job-duration-limit",
            help="Disable the per-job duration limit.",
        )
    )
    group.interfacy_help_position = 42
    group.interfacy_help_position_explicit = True

    help_text = group.get_help(click.Context(group))

    assert re.search(
        r"^\s*disable-job-duration-limit\s+Disable the per-job duration limit\.$",
        help_text,
        re.MULTILINE,
    )


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

    @pytest.mark.parametrize("parser", ["click_req_pos"], indirect=True)
    def test_single_top_level_class_command_namespace_and_run(self, parser):
        parser.add_command(Math)

        namespace = parser.parse_args(["pow", "2", "-e", "2"])

        assert namespace == {
            "rounding": 6,
            "command": "pow",
            "pow": {
                "base": 2,
                "exponent": 2,
            },
        }
        assert parser.run(args=["pow", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["click_req_pos"], indirect=True)
    def test_single_top_level_instance_command_namespace_and_run(self, parser):
        math = Math(rounding=2)
        parser.add_command(math)  # type: ignore[arg-type]

        namespace = parser.parse_args(["pow", "2", "-e", "2"])

        assert namespace == {
            "command": "pow",
            "pow": {
                "base": 2,
                "exponent": 2,
            },
        }
        assert parser.run(args=["pow", "2", "-e", "2"]) == 4


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

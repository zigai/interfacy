from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Literal
from unittest.mock import patch

import pytest

from interfacy import CommandGroup, Interfacy, Param
from interfacy.exceptions import DuplicateCommandError, UsageError
from interfacy.runtime.exit_codes import ExitCode


def test_any_and_object_parameters() -> None:
    """Verify that parameters typed as Any or object accept CLI input without error."""

    def echo(x: Any, y: object) -> dict[str, Any]:
        return {"x": x, "y": y}

    cli = Interfacy()
    cli.add_command(echo)
    res = cli.invoke(args=["hello", "world"])
    assert res == {"x": "hello", "y": "world"}


def test_argparse_error_formatting_no_trailing_quote() -> None:
    """Verify error messages for invalid choices do not contain stray quote marks."""

    def pick(choice: Literal["apple", "banana"] = "apple") -> str:
        return choice

    cli = Interfacy(backend="argparse")
    cli.add_command(pick)

    with pytest.raises(UsageError) as exc_info:
        cli.invoke(args=["--choice", "orange"])

    msg = str(exc_info.value)
    assert "invalid Literal['apple', 'banana'] value: 'orange'" in msg
    assert "Literal['apple', 'banana']\"" not in msg


def test_positional_parameter_named_underscore() -> None:
    """Verify positional parameter named '_' does not crash with IndexError."""

    def dummy(_: int) -> int:
        return _

    cli = Interfacy()
    cli.add_command(dummy)
    assert cli.invoke(args=["42"]) == 42


def test_single_letter_parameter_short_and_long_flags() -> None:
    """Verify single-letter parameter accepting both short and long flag does not collide with itself."""

    def configure(c: int = 1) -> int:
        return c

    cli = Interfacy()
    cli.add_command(configure, parameter_settings={"c": Param(flags=["-c", "--c"])})

    assert cli.invoke(args=["-c", "10"]) == 10
    assert cli.invoke(args=["--c", "20"]) == 20


def test_command_group_classmethod_and_staticmethod() -> None:
    """Verify classmethods and staticmethods in class commands inside CommandGroups execute cleanly."""

    class Service:
        @classmethod
        def clsmeth(cls) -> str:
            return "from_clsmeth"

        @staticmethod
        def statmeth() -> str:
            return "from_statmeth"

        def instmeth(self) -> str:
            return "from_instmeth"

    group = CommandGroup("svc")
    group.add_command(Service, include_classmethods=True, include_staticmethods=True)

    cli = Interfacy()
    cli.add_command(group)

    assert cli.invoke(args=["svc", "service", "clsmeth"]) == "from_clsmeth"
    assert cli.invoke(args=["svc", "service", "statmeth"]) == "from_statmeth"
    assert cli.invoke(args=["svc", "service", "instmeth"]) == "from_instmeth"


def test_command_group_subgroup_alias_collision() -> None:
    """Verify colliding subgroup aliases raise DuplicateCommandError during group registration."""
    root = CommandGroup("root")
    sub1 = CommandGroup("sub1", aliases=["shared"])
    sub2 = CommandGroup("sub2", aliases=["shared"])
    sub1.add_command(lambda: "pong1", name="ping")
    sub2.add_command(lambda: "pong2", name="ping")
    root.add_group(sub1)
    root.add_group(sub2)

    cli = Interfacy()
    with pytest.raises(DuplicateCommandError) as exc_info:
        cli.add_command(root)

    assert "shared" in str(exc_info.value)


def test_command_group_duplicate_alias_names_alias() -> None:
    """Verify duplicate alias on command inside CommandGroup reports the duplicated alias token."""
    group = CommandGroup("g")

    def my_cmd() -> None:
        pass

    group.add_command(my_cmd, aliases=["alias1", "alias1"])

    cli = Interfacy()
    with pytest.raises(DuplicateCommandError) as exc_info:
        cli.add_command(group)

    assert "alias1" in str(exc_info.value)


@dataclass
class PipedUser:
    name: str
    age: int


def test_piping_into_expanded_dataclass() -> None:
    """Verify piping JSON into a dataclass command with expand_model_params=True populates model."""

    def consume_user(user: PipedUser) -> PipedUser:
        return user

    cli = Interfacy(sys_exit_enabled=False)
    cli.add_command(consume_user, pipe_targets="user")

    payload = json.dumps({"name": "Alice", "age": 30})
    with patch("interfacy.engine.pipes.read_piped", return_value=payload):
        result = cli.invoke(args=[])
        assert result == PipedUser(name="Alice", age=30)


def test_async_cancelled_error_exits_with_interrupted() -> None:
    """Verify asyncio.CancelledError inside an async command cleanly exits with ExitCode.INTERRUPTED."""

    async def cancelled_cmd() -> None:
        task = asyncio.current_task()
        if task is not None:
            task.cancel()
        await asyncio.sleep(0.1)

    cli = Interfacy(sys_exit_enabled=True)
    cli.add_command(cancelled_cmd)

    with pytest.raises(SystemExit) as exc_info:
        cli.run(args=[])

    assert exc_info.value.code == ExitCode.INTERRUPTED


def test_print_result_with_sys_exit_disabled(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify print_result=True displays output when sys_exit_enabled=False."""

    def calc() -> int:
        return 42

    cli = Interfacy(print_result=True, sys_exit_enabled=False)
    cli.add_command(calc)

    res = cli.run(args=[])
    assert res == 42

    captured = capsys.readouterr()
    assert "42" in captured.out


def test_union_literal_with_open_type_allows_open_values() -> None:
    """Verify Union[Literal, int] allows both literal choices and open integer values."""

    def choose(val: Literal["a", "b"] | int) -> Literal["a", "b"] | int:
        return val

    cli = Interfacy()
    cli.add_command(choose)

    assert cli.invoke(args=["a"]) == "a"
    assert cli.invoke(args=["b"]) == "b"
    assert cli.invoke(args=["42"]) == 42

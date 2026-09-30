from collections.abc import Callable
from enum import Enum
from typing import Literal

import pytest

from interfacy import CommandGroup, Interfacy
from interfacy.exceptions import PipeInputError


# We define dummy functions here to use as command targets
def fn_single_arg(msg: str):
    return msg


def fn_multi_arg(a: str, b: str):
    return (a, b)


def fn_typed_arg(val: int):
    return val


def fn_dict_arg(data: dict):
    return data


def fn_partial(a: str, b: str | None = None):
    return (a, b)


def fn_default_msg(msg: str = "default"):
    return msg


class Greeter:
    def greet(self, msg: str = "default"):
        return msg


class TestPipeExecution:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    @pytest.mark.parametrize("nested", [False, True])
    @pytest.mark.parametrize(
        ("args", "priority", "expected"),
        [
            (["--value", "default"], "cli", "default"),
            ([], "cli", "piped"),
            (["--value", "default"], "pipe", "piped"),
        ],
    )
    def test_group_pipe_priority_tracks_explicit_defaults(
        self,
        parser: Interfacy,
        pipe_stdin: Callable[[str], None],
        nested: bool,
        args: list[str],
        priority: str,
        expected: str,
    ):
        def consume(value: str = "default"):
            return value

        root = CommandGroup("root")
        owner = root
        if nested:
            owner = CommandGroup("sub")
            root.add_group(owner)

        owner.add_command(consume, pipe_targets={"bindings": "value", "priority": priority})
        parser.add_command(root)
        pipe_stdin("piped")

        path = ["root", "sub"] if nested else ["root"]
        assert parser.invoke(args=[*path, "consume", *args]) == expected

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_single_target_pipe(self, parser: Interfacy, pipe_stdin):
        """Verify that a single argument receives piped input."""
        parser.add_command(fn_single_arg, pipe_targets="msg")
        pipe_stdin("hello world")

        assert parser.invoke(args=[]) == "hello world"

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_multi_target_newline(self, parser: Interfacy, pipe_stdin):
        """Verify checking splitting on newline."""
        parser.add_command(fn_multi_arg, pipe_targets=("a", "b"))

        pipe_stdin("foo\nbar")

        assert parser.invoke(args=[]) == ("foo", "bar")

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_required_pipe_target_errors_without_cli_or_stdin(
        self,
        parser: Interfacy,
        terminal_stdin: None,
    ):
        """Required pipe targets remain required when stdin is absent."""
        parser.add_command(fn_single_arg, pipe_targets="msg")

        with pytest.raises(PipeInputError):
            parser.invoke(args=[])

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_required_pipe_targets_accept_cli_without_stdin(
        self,
        parser: Interfacy,
        terminal_stdin: None,
    ):
        """CLI values satisfy required pipe targets when no stdin is present."""
        parser.add_command(fn_multi_arg, pipe_targets=("a", "b"))

        assert parser.invoke(args=["foo", "bar"]) == ("foo", "bar")

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_custom_delimiter(self, parser: Interfacy, pipe_stdin):
        """Verify custom delimiter."""
        # Use delimiter in pipe config
        parser.add_command(fn_multi_arg, pipe_targets={"bindings": ("a", "b"), "delimiter": ","})

        pipe_stdin("foo,bar")

        assert parser.invoke(args=[]) == ("foo", "bar")

    @pytest.mark.parametrize(
        ("parser", "args"),
        [
            ("argparse_req_pos", ["cli_value"]),
            ("argparse_kw_only", ["--msg", "cli_value"]),
        ],
        indirect=["parser"],
    )
    def test_priority_cli_overrides_pipe(self, parser: Interfacy, args: list[str], pipe_stdin):
        """Verify CLI args take precedence by default."""
        parser.add_command(fn_single_arg, pipe_targets="msg")

        pipe_stdin("piped")

        assert parser.invoke(args=args) == "cli_value"

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_priority_pipe_overrides_cli(self, parser: Interfacy, pipe_stdin):
        """Verify pipe overrides CLI when configured."""
        # Note: priority='pipe' means pipe wins.
        parser.add_command(fn_single_arg, pipe_targets={"bindings": "msg", "priority": "pipe"})

        pipe_stdin("piped_value")

        # Even if CLI provided, priority=pipe should overwrite
        # We pass a CLI value "cli_value". If pipe works, result is "piped_value"
        args = ["--msg", "cli_value"]
        assert parser.invoke(args=args) == "piped_value"

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_priority_cli_keeps_explicit_value_equal_to_default(
        self,
        parser: Interfacy,
        pipe_stdin,
    ):
        """Explicit CLI values win even when they equal the callable default."""
        parser.add_command(fn_default_msg, pipe_targets="msg")
        pipe_stdin("piped")

        assert parser.invoke(args=["--msg", "default"]) == "default"

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    @pytest.mark.parametrize(
        ("args", "expected"), [(["--msg", "default"], "default"), ([], "piped")]
    )
    def test_priority_cli_tracks_explicit_values_per_command(
        self,
        parser: Interfacy,
        pipe_stdin,
        args: list[str],
        expected: str,
    ):
        """Explicit CLI values are tracked for the selected command among several."""
        parser.add_command(fn_default_msg, pipe_targets="msg")
        parser.add_command(fn_single_arg)
        pipe_stdin("piped")

        assert parser.invoke(args=["fn-default-msg", *args]) == expected

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    @pytest.mark.parametrize(
        ("args", "expected"), [(["--msg", "default"], "default"), ([], "piped")]
    )
    def test_priority_cli_tracks_explicit_values_for_methods(
        self,
        parser: Interfacy,
        pipe_stdin,
        args: list[str],
        expected: str,
    ):
        """Explicit CLI values are tracked for a class method subcommand."""
        parser.add_command(Greeter)
        parser.pipe_to("msg", command="greeter", subcommand="greet")
        pipe_stdin("piped")

        assert parser.invoke(args=["greet", *args]) == expected

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_priority_cli_does_not_convert_unused_invalid_pipe_value(
        self,
        parser: Interfacy,
        pipe_stdin,
    ) -> None:
        def command(value: int = 3) -> int:
            return value

        parser.add_command(command, pipe_targets="value")
        pipe_stdin("not-an-integer")

        assert parser.invoke(args=["--value", "3"]) == 3

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_priority_pipe_converts_and_rejects_invalid_value(
        self,
        parser: Interfacy,
        pipe_stdin,
    ) -> None:
        def command(value: int = 3) -> int:
            return value

        parser.add_command(
            command,
            pipe_targets={"bindings": "value", "priority": "pipe"},
        )
        pipe_stdin("not-an-integer")

        with pytest.raises(PipeInputError, match="failed to convert piped input"):
            parser.invoke(args=["--value", "3"])

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_typed_conversion(self, parser: Interfacy, pipe_stdin):
        """Verify piped string is converted to target type (int)."""
        parser.add_command(fn_typed_arg, pipe_targets="val")

        pipe_stdin("42")

        assert parser.invoke(args=[]) == 42

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_partial_chunk_error(self, parser: Interfacy, pipe_stdin):
        """Verify error raised when fewer chunks than targets provided."""
        parser.add_command(fn_multi_arg, pipe_targets=("a", "b"))

        # Only one chunk provided for 2 targets
        pipe_stdin("one")

        with pytest.raises(PipeInputError):
            parser.invoke(args=[])

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_partial_chunk_allowed(self, parser: Interfacy, pipe_stdin):
        """Verify None filling when allow_partial is True."""
        # Use fn_partial which allows b=None
        parser.add_command(fn_partial, pipe_targets={"bindings": ("a", "b"), "allow_partial": True})

        # Only one chunk provided, second should be None
        pipe_stdin("one")

        assert parser.invoke(args=[]) == ("one", None)

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_excess_chunk_merged(self, parser: Interfacy, pipe_stdin):
        """Verify excess chunks are merged into the last target."""
        parser.add_command(fn_multi_arg, pipe_targets=("a", "b"))

        # 3 lines for 2 targets -> last target gets remainder
        pipe_stdin("one\ntwo\nthree")

        assert parser.invoke(args=[]) == ("one", "two\nthree")

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_complex_type_dict(self, parser: Interfacy, pipe_stdin):
        """Verify piped JSON string conversion to dict."""
        parser.add_command(fn_dict_arg, pipe_targets="data")

        pipe_stdin('{"key": 123}')

        assert parser.invoke(args=[]) == {"key": 123}

    @pytest.mark.parametrize("backend", ["argparse", "click"])
    def test_global_pipe_targets_relax_required_positional_before_parse(
        self,
        backend: str,
        pipe_stdin,
    ):
        parser = Interfacy(backend=backend, pipe_targets="msg")
        pipe_stdin("hello")

        assert parser.invoke(fn_single_arg, args=[]) == "hello"


# --- Piped List Tests ---


def fn_list_pipe(items: list[str]):
    """Function accepting a list for pipe testing."""
    return items


def fn_list_int_pipe(values: list[int]):
    """Function accepting a list of ints for pipe testing."""
    return values


class TestPipedListInput:
    """Tests for piping input to list parameters.

    With the improved is_cli_supplied logic, empty lists from argparse are
    treated as 'not supplied', so default priority='cli' works correctly.
    """

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_piped_list_newline_split(self, parser: Interfacy, pipe_stdin):
        """Verify piped newline data splits into list elements."""
        parser.add_command(fn_list_pipe, pipe_targets="items")

        pipe_stdin("alpha\nbeta\ngamma")

        result = parser.invoke(args=[])
        assert result == ["alpha", "beta", "gamma"]

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_piped_list_custom_delimiter(self, parser: Interfacy, pipe_stdin):
        """Verify custom delimiter splits into list elements."""
        parser.add_command(fn_list_pipe, pipe_targets={"bindings": "items", "delimiter": ","})

        pipe_stdin("x,y,z")

        result = parser.invoke(args=[])
        assert result == ["x", "y", "z"]

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_piped_list_int_conversion(self, parser: Interfacy, pipe_stdin):
        """Verify piped list elements are converted to target type."""
        parser.add_command(fn_list_int_pipe, pipe_targets="values")

        pipe_stdin("1\n2\n3")

        result = parser.invoke(args=[])
        assert result == [1, 2, 3]

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_piped_literal_list_rejects_invalid_values_before_execution(
        self,
        parser: Interfacy,
        pipe_stdin,
    ) -> None:
        executed = False

        def command(values: list[Literal["red", "blue"]]) -> list[str]:
            nonlocal executed
            executed = True

            return values

        parser.add_command(command, pipe_targets="values")
        pipe_stdin("green")

        with pytest.raises(PipeInputError, match="failed to convert piped input"):
            parser.invoke(args=[])

        assert executed is False

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_piped_literal_list_preserves_valid_values(
        self,
        parser: Interfacy,
        pipe_stdin,
    ) -> None:
        def command(values: list[Literal["red", "blue"]]) -> list[str]:
            return values

        parser.add_command(command, pipe_targets="values")
        pipe_stdin("red\nblue\nred")

        assert parser.invoke(args=[]) == ["red", "blue", "red"]

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_piped_enum_list_converts_each_value(
        self,
        parser: Interfacy,
        pipe_stdin,
    ) -> None:
        class Color(Enum):
            RED = "red"
            BLUE = "blue"

        def command(values: list[Color]) -> list[Color]:
            return values

        parser.add_command(command, pipe_targets="values")
        pipe_stdin("red\nblue")

        assert parser.invoke(args=[]) == [Color.RED, Color.BLUE]

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_piped_generic_and_union_types_conversion(self, parser: Interfacy, pipe_stdin):
        """Verify piped data converts to generic types (dict[str, int]) and unions (int | None)."""

        def fn_complex_pipe(data: dict[str, int], num: int | None):
            return data, num

        parser.add_command(fn_complex_pipe, pipe_targets=("data", "num"))
        pipe_stdin('{"a": 1}\n42')

        res_data, res_num = parser.invoke(args=[])
        assert isinstance(res_data, dict)
        assert res_data == {"a": 1}
        assert isinstance(res_num, int)
        assert res_num == 42

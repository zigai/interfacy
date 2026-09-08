import sys

import pytest

from interfacy import Interfacy
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


class TestPipeExecution:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_single_target_pipe(self, parser: Interfacy, mocker):
        """Verify that a single argument receives piped input."""
        parser.add_command(fn_single_arg, pipe_targets="msg")

        # Mock read_piped to return "hello world"
        # The key is to mock where it is IMPORTED/USED in the ArgumentParser/ArgparseRunner context
        # Interfacy.read_piped_input() calls read_piped() from interfacy.engine.pipes
        mocker.patch("interfacy.engine.pipes.read_piped", return_value="hello world")

        # We must call run() which triggers the runner and pipe logic.
        # Note: For single-command parsers, interfacy/argparse implies the command is selected implicitly.
        # We pass empty args list so pipe provides the value.
        assert parser.invoke(args=[]) == "hello world"

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_multi_target_newline(self, parser: Interfacy, mocker):
        """Verify checking splitting on newline."""
        parser.add_command(fn_multi_arg, pipe_targets=("a", "b"))

        mocker.patch("interfacy.engine.pipes.read_piped", return_value="foo\nbar")

        assert parser.invoke(args=[]) == ("foo", "bar")

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_required_pipe_target_errors_without_cli_or_stdin(
        self,
        parser: Interfacy,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Required pipe targets remain required when stdin is absent."""
        parser.add_command(fn_single_arg, pipe_targets="msg")
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

        with pytest.raises(PipeInputError):
            parser.invoke(args=[])

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_required_pipe_targets_accept_cli_without_stdin(
        self,
        parser: Interfacy,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """CLI values satisfy required pipe targets when no stdin is present."""
        parser.add_command(fn_multi_arg, pipe_targets=("a", "b"))
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

        assert parser.invoke(args=["foo", "bar"]) == ("foo", "bar")

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_custom_delimiter(self, parser: Interfacy, mocker):
        """Verify custom delimiter."""
        # Use delimiter in pipe config
        parser.add_command(fn_multi_arg, pipe_targets={"bindings": ("a", "b"), "delimiter": ","})

        mocker.patch("interfacy.engine.pipes.read_piped", return_value="foo,bar")

        assert parser.invoke(args=[]) == ("foo", "bar")

    @pytest.mark.parametrize(
        ("parser", "args"),
        [
            ("argparse_req_pos", ["cli_value"]),
            ("argparse_kw_only", ["--msg", "cli_value"]),
        ],
        indirect=["parser"],
    )
    def test_priority_cli_overrides_pipe(self, parser: Interfacy, args: list[str], mocker):
        """Verify CLI args take precedence by default."""
        parser.add_command(fn_single_arg, pipe_targets="msg")

        mocker.patch("interfacy.engine.pipes.read_piped", return_value="piped")

        assert parser.invoke(args=args) == "cli_value"

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_priority_pipe_overrides_cli(self, parser: Interfacy, mocker):
        """Verify pipe overrides CLI when configured."""
        # Note: priority='pipe' means pipe wins.
        parser.add_command(fn_single_arg, pipe_targets={"bindings": "msg", "priority": "pipe"})

        mocker.patch("interfacy.engine.pipes.read_piped", return_value="piped_value")

        # Even if CLI provided, priority=pipe should overwrite
        # We pass a CLI value "cli_value". If pipe works, result is "piped_value"
        args = ["--msg", "cli_value"]
        assert parser.invoke(args=args) == "piped_value"

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_priority_cli_keeps_explicit_value_equal_to_default(
        self,
        parser: Interfacy,
        mocker,
    ):
        """Explicit CLI values win even when they equal the callable default."""
        parser.add_command(fn_default_msg, pipe_targets="msg")
        mocker.patch("interfacy.engine.pipes.read_piped", return_value="piped")

        assert parser.invoke(args=["--msg", "default"]) == "default"

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_typed_conversion(self, parser: Interfacy, mocker):
        """Verify piped string is converted to target type (int)."""
        parser.add_command(fn_typed_arg, pipe_targets="val")

        mocker.patch("interfacy.engine.pipes.read_piped", return_value="42")

        assert parser.invoke(args=[]) == 42

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_partial_chunk_error(self, parser: Interfacy, mocker):
        """Verify error raised when fewer chunks than targets provided."""
        parser.add_command(fn_multi_arg, pipe_targets=("a", "b"))

        # Only one chunk provided for 2 targets
        mocker.patch("interfacy.engine.pipes.read_piped", return_value="one")

        with pytest.raises(PipeInputError):
            parser.invoke(args=[])

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_partial_chunk_allowed(self, parser: Interfacy, mocker):
        """Verify None filling when allow_partial is True."""
        # Use fn_partial which allows b=None
        parser.add_command(fn_partial, pipe_targets={"bindings": ("a", "b"), "allow_partial": True})

        # Only one chunk provided, second should be None
        mocker.patch("interfacy.engine.pipes.read_piped", return_value="one")

        assert parser.invoke(args=[]) == ("one", None)

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_excess_chunk_merged(self, parser: Interfacy, mocker):
        """Verify excess chunks are merged into the last target."""
        parser.add_command(fn_multi_arg, pipe_targets=("a", "b"))

        # 3 lines for 2 targets -> last target gets remainder
        mocker.patch("interfacy.engine.pipes.read_piped", return_value="one\ntwo\nthree")

        assert parser.invoke(args=[]) == ("one", "two\nthree")

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_complex_type_dict(self, parser: Interfacy, mocker):
        """Verify piped JSON string conversion to dict."""
        parser.add_command(fn_dict_arg, pipe_targets="data")

        mocker.patch("interfacy.engine.pipes.read_piped", return_value='{"key": 123}')

        assert parser.invoke(args=[]) == {"key": 123}

    @pytest.mark.parametrize("backend", ["argparse", "click"])
    def test_global_pipe_targets_relax_required_positional_before_parse(
        self,
        backend: str,
        mocker,
    ):
        parser = Interfacy(backend=backend, pipe_targets="msg")
        mocker.patch("interfacy.engine.pipes.read_piped", return_value="hello")

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
    def test_piped_list_newline_split(self, parser: Interfacy, mocker):
        """Verify piped newline data splits into list elements."""
        parser.add_command(fn_list_pipe, pipe_targets="items")

        mocker.patch("interfacy.engine.pipes.read_piped", return_value="alpha\nbeta\ngamma")

        result = parser.invoke(args=[])
        assert result == ["alpha", "beta", "gamma"]

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_piped_list_custom_delimiter(self, parser: Interfacy, mocker):
        """Verify custom delimiter splits into list elements."""
        parser.add_command(fn_list_pipe, pipe_targets={"bindings": "items", "delimiter": ","})

        mocker.patch("interfacy.engine.pipes.read_piped", return_value="x,y,z")

        result = parser.invoke(args=[])
        assert result == ["x", "y", "z"]

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_piped_list_int_conversion(self, parser: Interfacy, mocker):
        """Verify piped list elements are converted to target type."""
        parser.add_command(fn_list_int_pipe, pipe_targets="values")

        mocker.patch("interfacy.engine.pipes.read_piped", return_value="1\n2\n3")

        result = parser.invoke(args=[])
        assert result == [1, 2, 3]

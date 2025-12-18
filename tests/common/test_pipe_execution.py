import pytest
from interfacy.core import InterfacyParser, PipeTargets
from interfacy.exceptions import PipeInputError
from unittest.mock import Mock


# We define dummy functions here to use as command targets
def fn_single_arg(msg: str):
    return msg


def fn_multi_arg(a: str, b: str):
    return (a, b)


def fn_typed_arg(val: int):
    return val


def fn_dict_arg(data: dict):
    return data


def fn_partial(a: str, b: str = None):
    return (a, b)


class TestPipeExecution:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_single_target_pipe(self, parser: InterfacyParser, mocker):
        """Verify that a single argument receives piped input."""
        parser.add_command(fn_single_arg, pipe_targets="msg")

        # Mock read_piped to return "hello world"
        # The key is to mock where it is IMPORTED/USED in the ArgumentParser/ArgparseRunner context
        # Argparser.read_piped_input() calls read_piped() from interfacy.core
        mocker.patch("interfacy.core.read_piped", return_value="hello world")

        # We must call run() which triggers the runner and pipe logic.
        # Note: For single-command parsers, interfacy/argparse implies the command is selected implicitly.
        # We pass empty args list so pipe provides the value.
        assert parser.run(args=[]) == "hello world"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_multi_target_newline(self, parser: InterfacyParser, mocker):
        """Verify checking splitting on newline."""
        parser.add_command(fn_multi_arg, pipe_targets=("a", "b"))

        mocker.patch("interfacy.core.read_piped", return_value="foo\nbar")

        assert parser.run(args=[]) == ("foo", "bar")

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_custom_delimiter(self, parser: InterfacyParser, mocker):
        """Verify custom delimiter."""
        # Use delimiter in pipe config
        parser.add_command(fn_multi_arg, pipe_targets={"bindings": ("a", "b"), "delimiter": ","})

        mocker.patch("interfacy.core.read_piped", return_value="foo,bar")

        assert parser.run(args=[]) == ("foo", "bar")

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
    def test_priority_cli_overrides_pipe(self, parser: InterfacyParser, mocker):
        """Verify CLI args take precedence by default."""
        parser.add_command(fn_single_arg, pipe_targets="msg")

        mocker.patch("interfacy.core.read_piped", return_value="piped")

        # Pass explicit CLI argument
        match parser.flag_strategy.style:
            case "required_positional":
                args = ["cli_value"]
            case "keyword_only":
                args = ["--msg", "cli_value"]
            case _:
                pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

        assert parser.run(args=args) == "cli_value"

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_priority_pipe_overrides_cli(self, parser: InterfacyParser, mocker):
        """Verify pipe overrides CLI when configured."""
        # Note: priority='pipe' means pipe wins.
        parser.add_command(fn_single_arg, pipe_targets={"bindings": "msg", "priority": "pipe"})

        mocker.patch("interfacy.core.read_piped", return_value="piped_value")

        # Even if CLI provided, priority=pipe should overwrite
        # We pass a CLI value "cli_value". If pipe works, result is "piped_value"
        args = ["--msg", "cli_value"]
        assert parser.run(args=args) == "piped_value"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_typed_conversion(self, parser: InterfacyParser, mocker):
        """Verify piped string is converted to target type (int)."""
        parser.add_command(fn_typed_arg, pipe_targets="val")

        mocker.patch("interfacy.core.read_piped", return_value="42")

        assert parser.run(args=[]) == 42

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_partial_chunk_error(self, parser: InterfacyParser, mocker):
        """Verify error raised when fewer chunks than targets provided."""
        parser.add_command(fn_multi_arg, pipe_targets=("a", "b"))

        # Only one chunk provided for 2 targets
        mocker.patch("interfacy.core.read_piped", return_value="one")

        # Argparser catches Interfacy errors and returns them (since sys_exit=False in tests)
        result = parser.run(args=[])
        assert isinstance(result, PipeInputError)

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_partial_chunk_allowed(self, parser: InterfacyParser, mocker):
        """Verify None filling when allow_partial is True."""
        # Use fn_partial which allows b=None
        parser.add_command(fn_partial, pipe_targets={"bindings": ("a", "b"), "allow_partial": True})

        # Only one chunk provided, second should be None
        mocker.patch("interfacy.core.read_piped", return_value="one")

        assert parser.run(args=[]) == ("one", None)

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_excess_chunk_merged(self, parser: InterfacyParser, mocker):
        """Verify excess chunks are merged into the last target."""
        parser.add_command(fn_multi_arg, pipe_targets=("a", "b"))

        # 3 lines for 2 targets -> last target gets remainder
        mocker.patch("interfacy.core.read_piped", return_value="one\ntwo\nthree")

        assert parser.run(args=[]) == ("one", "two\nthree")

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_complex_type_dict(self, parser: InterfacyParser, mocker):
        """Verify piped JSON string conversion to dict."""
        parser.add_command(fn_dict_arg, pipe_targets="data")

        mocker.patch("interfacy.core.read_piped", return_value='{"key": 123}')

        assert parser.run(args=[]) == {"key": 123}


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

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_piped_list_newline_split(self, parser: InterfacyParser, mocker):
        """Verify piped newline data splits into list elements."""
        parser.add_command(fn_list_pipe, pipe_targets="items")

        mocker.patch("interfacy.core.read_piped", return_value="alpha\nbeta\ngamma")

        result = parser.run(args=[])
        assert result == ["alpha", "beta", "gamma"]

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_piped_list_custom_delimiter(self, parser: InterfacyParser, mocker):
        """Verify custom delimiter splits into list elements."""
        parser.add_command(fn_list_pipe, pipe_targets={"bindings": "items", "delimiter": ","})

        mocker.patch("interfacy.core.read_piped", return_value="x,y,z")

        result = parser.run(args=[])
        assert result == ["x", "y", "z"]

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_piped_list_int_conversion(self, parser: InterfacyParser, mocker):
        """Verify piped list elements are converted to target type."""
        parser.add_command(fn_list_int_pipe, pipe_targets="values")

        mocker.patch("interfacy.core.read_piped", return_value="1\n2\n3")

        result = parser.run(args=[])
        assert result == [1, 2, 3]

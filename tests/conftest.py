import io
import sys
from collections.abc import Callable

import pytest

from interfacy import Interfacy
from interfacy.naming import DefaultFlagStrategy


@pytest.fixture
def parser(request: pytest.FixtureRequest) -> Interfacy:
    fixture_name = request.param
    return request.getfixturevalue(fixture_name)


@pytest.fixture
def argparse_req_pos() -> Interfacy:
    parser = Interfacy(
        backend="argparse",
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        full_error_traceback=True,
        help_layout=None,
        print_result=True,
    )
    parser.metadata["flag_style"] = "required_positional"
    return parser


@pytest.fixture
def argparse_kw_only() -> Interfacy:
    parser = Interfacy(
        backend="argparse",
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        full_error_traceback=True,
        help_layout=None,
        print_result=True,
    )
    parser.metadata["flag_style"] = "keyword_only"
    return parser


@pytest.fixture
def click_req_pos() -> Interfacy:
    pytest.importorskip("click")
    parser = Interfacy(
        backend="click",
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        full_error_traceback=True,
        help_layout=None,
        print_result=True,
    )
    parser.metadata["flag_style"] = "required_positional"

    return parser


@pytest.fixture
def click_kw_only() -> Interfacy:
    pytest.importorskip("click")
    parser = Interfacy(
        backend="click",
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        full_error_traceback=True,
        help_layout=None,
        print_result=True,
    )
    parser.metadata["flag_style"] = "keyword_only"

    return parser


class TerminalStdin(io.StringIO):
    def isatty(self) -> bool:
        return True


@pytest.fixture
def pipe_stdin(monkeypatch: pytest.MonkeyPatch) -> Callable[[str], None]:
    """Feed text through a non-terminal stdin; call again before each invoke that reads it."""

    def feed(text: str) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(text))

    return feed


@pytest.fixture
def terminal_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", TerminalStdin())


@pytest.fixture
def schema_parser(argparse_req_pos: Interfacy) -> Interfacy:
    """Parser for registration and schema assertions that do not depend on a backend."""
    return argparse_req_pos

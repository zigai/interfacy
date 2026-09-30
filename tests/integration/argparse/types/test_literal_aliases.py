from __future__ import annotations

import sys
from typing import Any, Literal

import pytest

from interfacy import Interfacy
from interfacy.exceptions import UsageError

StatusAlias = Literal["OPEN", "CLOSED", "PENDING"]


def _build_assignment_alias_fn():
    def fn(status: StatusAlias):
        return status

    return fn


def _build_pep695_alias_fn():
    if sys.version_info < (3, 12):
        pytest.skip("PEP 695 type aliases require Python 3.12+")
    namespace: dict[str, Any] = {}
    code = "\n".join(
        [
            "from typing import Literal",
            "type LogLevel = Literal['DEBUG', 'INFO', 'WARNING', 'ERROR']",
            "def fn(log_level: LogLevel):",
            "    return log_level",
        ]
    )
    exec(code, namespace, namespace)

    return namespace["fn"]


def _build_future_annotations_alias_fn():
    namespace: dict[str, Any] = {}
    code = "\n".join(
        [
            "from __future__ import annotations",
            "from typing import Literal",
            "StartTarget = Literal['backend', 'frontend']",
            "def fn(target: StartTarget = 'backend'):",
            "    return target",
        ]
    )
    exec(code, namespace, namespace)

    return namespace["fn"]


@pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
def test_literal_assignment_alias_parsing(parser: Interfacy):
    fn = _build_assignment_alias_fn()
    parser.add_command(fn)

    match parser.metadata["flag_style"]:
        case "required_positional":
            args = ["OPEN"]
        case "keyword_only":
            args = ["--status", "OPEN"]
        case _:
            pytest.fail(f"Unhandled flag strategy: {parser.metadata['flag_style']}")

    assert parser.invoke(args=args) == "OPEN"


@pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
def test_literal_assignment_alias_rejects_invalid_choice(parser: Interfacy):
    fn = _build_assignment_alias_fn()
    parser.add_command(fn)

    with pytest.raises(UsageError):
        parser.parse_args(["--status", "UNKNOWN"])


@pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
def test_pep695_literal_alias_parsing(parser: Interfacy):
    fn = _build_pep695_alias_fn()
    parser.add_command(fn)

    match parser.metadata["flag_style"]:
        case "required_positional":
            args = ["INFO"]
        case "keyword_only":
            args = ["--log-level", "INFO"]
        case _:
            pytest.fail(f"Unhandled flag strategy: {parser.metadata['flag_style']}")

    assert parser.invoke(args=args) == "INFO"


@pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
def test_pep695_literal_alias_rejects_invalid_choice(parser: Interfacy):
    fn = _build_pep695_alias_fn()
    parser.add_command(fn)

    with pytest.raises(UsageError):
        parser.parse_args(["--log-level", "TRACE"])


@pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
def test_future_annotations_literal_alias_parsing(parser: Interfacy):
    fn = _build_future_annotations_alias_fn()
    parser.add_command(fn)

    match parser.metadata["flag_style"]:
        case "required_positional":
            args = ["--target", "backend"]
        case "keyword_only":
            args = ["--target", "backend"]
        case _:
            pytest.fail(f"Unhandled flag strategy: {parser.metadata['flag_style']}")

    assert parser.invoke(args=args) == "backend"


@pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
def test_future_annotations_literal_alias_rejects_invalid_choice(parser: Interfacy):
    fn = _build_future_annotations_alias_fn()
    parser.add_command(fn)

    with pytest.raises(UsageError):
        parser.parse_args(["--target", "unknown"])


def test_union_literal_with_open_type_allows_open_values() -> None:
    """Verify Union[Literal, int] allows both literal choices and open integer values."""

    def choose(val: Literal["a", "b"] | int) -> Literal["a", "b"] | int:
        return val

    cli = Interfacy()
    cli.add_command(choose)

    assert cli.invoke(args=["a"]) == "a"
    assert cli.invoke(args=["b"]) == "b"
    assert cli.invoke(args=["42"]) == 42


def test_invalid_literal_error_names_value_without_stray_quote() -> None:
    """Verify error messages for invalid choices do not contain stray quote marks."""

    def pick(choice: Literal["apple", "banana"] = "apple") -> str:
        return choice

    cli = Interfacy(backend="argparse")
    cli.add_command(pick)

    with pytest.raises(UsageError) as exc_info:
        cli.invoke(args=["--choice", "orange"])

    message = str(exc_info.value)
    assert "'orange'" in message
    assert '"' not in message

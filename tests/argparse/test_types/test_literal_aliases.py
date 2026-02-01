import sys
from typing import Any, Literal

import pytest

from interfacy.core import InterfacyParser

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
def test_literal_assignment_alias_parsing(parser: InterfacyParser):
    fn = _build_assignment_alias_fn()
    parser.add_command(fn)

    match parser.flag_strategy.style:
        case "required_positional":
            args = ["OPEN"]
        case "keyword_only":
            args = ["--status", "OPEN"]
        case _:
            pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

    assert parser.run(args=args) == "OPEN"


@pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
def test_literal_assignment_alias_populates_choices(parser: InterfacyParser):
    fn = _build_assignment_alias_fn()
    parser.add_command(fn)

    arg_parser = parser.build_parser()
    action = next(a for a in arg_parser._actions if getattr(a, "dest", None) == "status")
    assert action.choices is not None
    assert set(action.choices) == {"OPEN", "CLOSED", "PENDING"}


@pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
def test_literal_assignment_alias_rejects_invalid_choice(parser: InterfacyParser):
    fn = _build_assignment_alias_fn()
    parser.add_command(fn)

    with pytest.raises(SystemExit):
        parser.parse_args(["--status", "UNKNOWN"])


@pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
def test_pep695_literal_alias_parsing(parser: InterfacyParser):
    fn = _build_pep695_alias_fn()
    parser.add_command(fn)

    match parser.flag_strategy.style:
        case "required_positional":
            args = ["INFO"]
        case "keyword_only":
            args = ["--log-level", "INFO"]
        case _:
            pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

    assert parser.run(args=args) == "INFO"


@pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
def test_pep695_literal_alias_populates_choices(parser: InterfacyParser):
    fn = _build_pep695_alias_fn()
    parser.add_command(fn)

    arg_parser = parser.build_parser()
    action = next(a for a in arg_parser._actions if getattr(a, "dest", None) == "log_level")
    assert action.choices is not None
    assert set(action.choices) == {"DEBUG", "INFO", "WARNING", "ERROR"}


@pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
def test_pep695_literal_alias_rejects_invalid_choice(parser: InterfacyParser):
    fn = _build_pep695_alias_fn()
    parser.add_command(fn)

    with pytest.raises(SystemExit):
        parser.parse_args(["--log-level", "TRACE"])


@pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
def test_future_annotations_literal_alias_parsing(parser: InterfacyParser):
    fn = _build_future_annotations_alias_fn()
    parser.add_command(fn)

    match parser.flag_strategy.style:
        case "required_positional":
            args = ["--target", "backend"]
        case "keyword_only":
            args = ["--target", "backend"]
        case _:
            pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

    assert parser.run(args=args) == "backend"


@pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
def test_future_annotations_literal_alias_populates_choices(parser: InterfacyParser):
    fn = _build_future_annotations_alias_fn()
    parser.add_command(fn)

    arg_parser = parser.build_parser()
    action = next(a for a in arg_parser._actions if getattr(a, "dest", None) == "target")
    assert action.choices is not None
    assert set(action.choices) == {"backend", "frontend"}


@pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
def test_future_annotations_literal_alias_rejects_invalid_choice(parser: InterfacyParser):
    fn = _build_future_annotations_alias_fn()
    parser.add_command(fn)

    with pytest.raises(SystemExit):
        parser.parse_args(["--target", "unknown"])

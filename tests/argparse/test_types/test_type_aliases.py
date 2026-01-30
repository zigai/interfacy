import typing
from typing import Literal

import pytest

from interfacy.core import InterfacyParser


def _make_literal_alias() -> object:
    if not hasattr(typing, "TypeAliasType"):
        pytest.skip("TypeAliasType not available on this Python version")
    return typing.TypeAliasType("Level", Literal["LOW", "MEDIUM", "HIGH"])  # type: ignore[attr-defined]


def _build_literal_alias_fn(alias: object):
    def fn(level: alias):  # type: ignore[misc,valid-type]
        return level

    return fn


@pytest.mark.parametrize("parser", ["argparse_req_pos", "argparse_kw_only"], indirect=True)
def test_literal_type_alias_parsing(parser: InterfacyParser):
    alias = _make_literal_alias()
    fn = _build_literal_alias_fn(alias)
    parser.add_command(fn)

    match parser.flag_strategy.style:
        case "required_positional":
            args = ["LOW"]
        case "keyword_only":
            args = ["--level", "LOW"]
        case _:
            pytest.fail(f"Unhandled flag strategy: {parser.flag_strategy.style}")

    assert parser.run(args=args) == "LOW"


@pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
def test_literal_type_alias_populates_choices(parser: InterfacyParser):
    alias = _make_literal_alias()
    fn = _build_literal_alias_fn(alias)
    parser.add_command(fn)

    arg_parser = parser.build_parser()
    action = next(a for a in arg_parser._actions if getattr(a, "dest", None) == "level")
    assert action.choices is not None
    assert set(action.choices) == {"LOW", "MEDIUM", "HIGH"}

from dataclasses import dataclass

import pytest
from strto import StrToTypeParser

from interfacy import Interfacy


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_custom_type_parser_without_list_is_not_mutated(backend: str) -> None:
    """Interfacy should parse lists without adding list support to caller parsers."""
    custom = StrToTypeParser(parsers={int: int}, from_file=False)

    def total(values: list[int]) -> int:
        return sum(values)

    parser = Interfacy(backend=backend, type_parser=custom)

    assert parser.invoke(total, args=["1", "2"]) == 3
    assert custom.parsers == {int: int}


def test_interfacy_add_type_parser_registers_custom_parser() -> None:
    """Custom parsers can be added without replacing Interfacy's default parser."""

    @dataclass(frozen=True)
    class Repository:
        owner: str
        name: str

    def parse_repository(raw: str) -> Repository:
        owner, _, name = raw.partition("/")
        return Repository(owner=owner, name=name)

    def command(repo: Repository) -> str:
        return f"{repo.owner}:{repo.name}"

    parser = Interfacy()
    parser.add_type_parser(Repository, parse_repository)

    assert parser.invoke(command, args=["zigai/interfacy"]) == "zigai:interfacy"

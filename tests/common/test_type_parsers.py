import datetime
from dataclasses import dataclass

from strto import StrToTypeParser

from interfacy import Interfacy
from interfacy.argparse_backend import Argparser
from interfacy.click_backend import ClickParser
from interfacy.type_parsers import build_default_type_parser


def test_build_default_type_parser_matches_interfacy_defaults_except_list():
    """Interfacy's default parser should mirror strto defaults except for list."""
    parser = build_default_type_parser(from_file=False)

    assert parser.from_file is False
    assert list not in parser.parsers
    assert int in parser.parsers
    assert tuple in parser.parsers
    assert dict in parser.parsers
    assert datetime.datetime in parser.parsers


def test_argparser_custom_type_parser_without_list_is_accepted_unchanged():
    """Argparser should not mutate or require list support on caller parsers."""
    custom = StrToTypeParser(parsers={int: int}, from_file=False)

    parser = Argparser(type_parser=custom, sys_exit_enabled=False)

    assert parser.type_parser is custom
    assert parser.type_parser.parsers == {int: int}
    assert list not in custom.parsers


def test_clickparser_custom_type_parser_without_list_is_accepted_unchanged():
    """ClickParser should not mutate or require list support on caller parsers."""
    custom = StrToTypeParser(parsers={int: int}, from_file=False)

    parser = ClickParser(type_parser=custom, sys_exit_enabled=False)

    assert parser.type_parser is custom
    assert parser.type_parser.parsers == {int: int}
    assert list not in custom.parsers


def test_default_interfacy_parsers_omit_list_for_both_backends():
    """Both backends should now start from the same Interfacy-owned default parser set."""
    argparse_parser = Argparser(sys_exit_enabled=False)
    click_parser = ClickParser(sys_exit_enabled=False)

    assert list not in argparse_parser.type_parser.parsers
    assert list not in click_parser.type_parser.parsers
    assert argparse_parser.type_parser.from_file is True
    assert click_parser.type_parser.from_file is True


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

    parser = Interfacy(sys_exit_enabled=False)
    parser.add_type_parser(Repository, parse_repository)

    assert parser.run(command, args=["zigai/interfacy"]) == "zigai:interfacy"


def test_interfacy_type_parser_argument_still_replaces_parser() -> None:
    """The constructor still supports replacing the full type parser."""
    custom = StrToTypeParser(parsers={int: int}, from_file=False)
    parser = Interfacy(type_parser=custom, sys_exit_enabled=False)

    assert parser.type_parser is custom
    assert parser.type_parser.parsers == {int: int}

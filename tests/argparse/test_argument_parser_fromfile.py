from __future__ import annotations

from pathlib import Path

from interfacy.argparse_backend import Argparser
from interfacy.argparse_backend.argument_parser import ArgumentParser


def test_argument_parser_fromfile_prefix_expands(tmp_path: Path) -> None:
    args_file = tmp_path / "args.txt"
    args_file.write_text("Hello, world!\n", encoding="utf-8")

    parser = ArgumentParser(fromfile_prefix_chars="@")
    parser.add_argument("value")

    parsed = parser.parse_args([f"@{args_file}"])
    assert parsed.value == "Hello, world!"


def test_argument_parser_fromfile_prefix_none_is_literal() -> None:
    parser = ArgumentParser(fromfile_prefix_chars=None)
    parser.add_argument("value")

    parsed = parser.parse_args(["@literal"])
    assert parsed.value == "@literal"


def test_argparser_respects_allow_args_from_file(tmp_path: Path) -> None:
    def archive(source: str, destination: str, compress: bool = False) -> tuple[str, str, bool]:
        return source, destination, compress

    def echo(value: str) -> str:
        return value

    args_file = tmp_path / "archive.args"
    args_file.write_text("logs\nbackup.zip\n--compress\n", encoding="utf-8")

    parser = Argparser(sys_exit_enabled=False)
    parser.add_command(archive)

    literal_parser = Argparser(sys_exit_enabled=False, allow_args_from_file=False)
    literal_parser.add_command(echo)

    assert parser.run(args=[f"@{args_file}"]) == ("logs", "backup.zip", True)
    assert literal_parser.run(args=[f"@{args_file}"]) == f"@{args_file}"

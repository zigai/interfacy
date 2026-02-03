from __future__ import annotations

from pathlib import Path

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

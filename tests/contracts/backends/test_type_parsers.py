import asyncio
import logging
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

import click
import pytest
from strto import StrToTypeParser

from interfacy import CommandGroup, Interfacy
from interfacy.common.debug import get_logger
from interfacy.exceptions import UsageError


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


class ManagedInput:
    def __init__(self, handle: TextIO) -> None:
        self.handle = handle


@pytest.fixture
def managed_input_parser(
    tmp_path: Path,
) -> Generator[tuple[Interfacy, Path, list[TextIO]], None, None]:
    path = tmp_path / "input.txt"
    path.write_text("payload", encoding="utf-8")
    handles: list[TextIO] = []
    parser = Interfacy(backend="click")

    def parse_input(value: str) -> ManagedInput:
        handle = click.File("r", encoding="utf-8").convert(value, None, click.get_current_context())
        handles.append(handle)
        return ManagedInput(handle)

    parser.add_type_parser(ManagedInput, parse_input)
    try:
        yield parser, path, handles
    finally:
        for handle in handles:
            handle.close()


@pytest.mark.parametrize("grouped", [False, True])
def test_click_conversion_resources_stay_open_during_invocation_and_close_afterward(
    managed_input_parser: tuple[Interfacy, Path, list[TextIO]],
    grouped: bool,
) -> None:
    parser, path, handles = managed_input_parser

    def command(source: ManagedInput) -> str:
        assert not source.handle.closed
        return source.handle.read()

    if grouped:
        group = CommandGroup("files")
        group.add_command(command, name="read")
        result = parser.invoke(group, args=["files", "read", str(path)])
    else:
        result = parser.invoke(command, args=[str(path)])

    assert result == "payload"
    assert handles
    assert all(handle.closed for handle in handles)


def test_click_conversion_resources_are_owned_by_parsed_arguments(
    managed_input_parser: tuple[Interfacy, Path, list[TextIO]],
) -> None:
    parser, path, handles = managed_input_parser

    def command(source: ManagedInput) -> str:
        return source.handle.read()

    parser.add_command(command)
    with parser.parse_args(args=[str(path)]) as arguments:
        source = arguments["source"]
        assert isinstance(source, ManagedInput)
        assert not source.handle.closed
        assert source.handle.read() == "payload"

    assert handles
    assert all(handle.closed for handle in handles)


def test_click_conversion_resources_close_when_parsing_fails(
    managed_input_parser: tuple[Interfacy, Path, list[TextIO]],
) -> None:
    parser, path, handles = managed_input_parser

    def command(source: ManagedInput, count: int) -> None:
        pytest.fail("Invalid input must not execute the command")

    with pytest.raises(UsageError):
        parser.invoke(command, args=[str(path), "invalid"])

    assert handles
    assert all(handle.closed for handle in handles)


def test_click_conversion_resources_close_when_command_fails(
    managed_input_parser: tuple[Interfacy, Path, list[TextIO]],
) -> None:
    parser, path, handles = managed_input_parser
    failure = RuntimeError("command failed")

    def command(source: ManagedInput) -> None:
        assert not source.handle.closed
        raise failure

    with pytest.raises(RuntimeError) as e:
        parser.invoke(command, args=[str(path)])

    assert e.value is failure
    assert handles
    assert all(handle.closed for handle in handles)


@pytest.mark.parametrize(
    "cleanup_error", [RuntimeError("synthetic-cleanup-payload"), asyncio.CancelledError()]
)
def test_click_conversion_cleanup_failure_preserves_command_failure(
    managed_input_parser: tuple[Interfacy, Path, list[TextIO]],
    cleanup_error: BaseException,
    caplog: pytest.LogCaptureFixture,
) -> None:
    parser, path, handles = managed_input_parser
    convert_input = parser.type_parser.parsers[ManagedInput]
    failure = ValueError("command failed")

    def fail_cleanup() -> None:
        raise cleanup_error

    def parse_input(value: str) -> ManagedInput:
        source = convert_input(value)
        click.get_current_context().call_on_close(fail_cleanup)
        return source

    def command(source: ManagedInput) -> None:
        assert not source.handle.closed
        raise failure

    parser.add_type_parser(ManagedInput, parse_input)
    logger = get_logger("interfacy.common.resources")
    logger.addHandler(caplog.handler)
    try:
        with (
            caplog.at_level(logging.WARNING, logger=logger.name),
            pytest.raises(ValueError, match="command failed") as e,
        ):
            parser.invoke(command, args=[str(path)])
    finally:
        logger.removeHandler(caplog.handler)

    assert e.value is failure
    assert handles
    assert all(handle.closed for handle in handles)
    assert "Resource cleanup failed" in caplog.text
    assert "synthetic-cleanup-payload" not in caplog.text


def test_click_conversion_resources_close_on_async_cancellation(
    managed_input_parser: tuple[Interfacy, Path, list[TextIO]],
) -> None:
    parser, path, handles = managed_input_parser

    async def scenario() -> None:
        started = asyncio.Event()
        release = asyncio.Event()

        async def command(source: ManagedInput) -> None:
            assert not source.handle.closed
            started.set()
            await release.wait()

        invocation = asyncio.create_task(parser.invoke_async(command, args=[str(path)]))
        await started.wait()
        invocation.cancel()
        with pytest.raises(asyncio.CancelledError):
            await invocation

    asyncio.run(scenario())

    assert handles
    assert all(handle.closed for handle in handles)

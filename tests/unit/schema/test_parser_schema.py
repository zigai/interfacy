from objinspect import Function

from interfacy.schema.schema import Command, ParserSchema
from tests.unit.schema.conftest import make_command_stub


def sample() -> None:
    """Sample docstring."""


def another() -> None:
    """Another docstring."""


def test_parser_schema_exposes_raw_description_and_epilog() -> None:
    commands = {"sample": make_command_stub(Function(sample))}
    schema = ParserSchema(
        raw_description="Top level description",
        raw_epilog="Tail text",
        commands=commands,
        command_key="command",
        allow_args_from_file=True,
        pipe_targets=None,
    )

    assert schema.description == "Top level description"
    assert schema.epilog == "Tail text"


def test_parser_schema_handles_missing_description_and_epilog() -> None:
    commands = {"sample": make_command_stub(Function(sample))}
    schema = ParserSchema(
        raw_description=None,
        raw_epilog=None,
        commands=commands,
        command_key="command",
        allow_args_from_file=False,
        pipe_targets=None,
        metadata={"source": "tests"},
    )

    assert schema.description is None
    assert schema.epilog is None
    assert schema.allow_args_from_file is False
    assert schema.metadata == {"source": "tests"}


def test_multi_command_schema_reports_command_names() -> None:
    commands = {
        "sample": make_command_stub(Function(sample)),
        "another": make_command_stub(Function(another)),
    }
    schema = ParserSchema(
        raw_description=None,
        raw_epilog=None,
        commands=commands,
        command_key=None,
        allow_args_from_file=True,
        pipe_targets=None,
    )

    assert schema.is_multi_command is True
    assert schema.canonical_names == ("sample", "another")
    assert schema.command_key is None


def test_command_description_and_epilog_helpers() -> None:
    command = Command(
        obj=Function(sample),
        canonical_name="sample",
        cli_name="sample",
        aliases=(),
        raw_description="Command level",
        raw_epilog="Command epilog",
    )

    assert command.description == "Command level"
    assert command.epilog == "Command epilog"

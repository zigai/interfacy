from objinspect import Function

from interfacy.schema.schema import Command, ParserSchema
from tests.schema.conftest import (
    RecordingHelpLayout,
    make_command_stub,
)


def sample() -> None:
    """sample docstring"""


def another() -> None:
    """another docstring"""


def test_parser_schema_formats_description_and_epilog_once() -> None:
    """Verify that descriptions and epilogs are formatted correctly and cached."""
    layout = RecordingHelpLayout()
    commands = {
        "sample": make_command_stub(
            Function(sample),
            layout=layout,
        )
    }

    schema = ParserSchema(
        raw_description="Top level description",
        raw_epilog="Tail text",
        commands=commands,
        command_key="command",
        allow_args_from_file=True,
        pipe_targets=None,
        theme=layout,
    )

    assert schema.description == "formatted::Top level description"
    assert schema.description is schema.description  # cached_property guard
    assert schema.epilog == "formatted::Tail text"
    assert layout.formatted_descriptions[:1] == ["Top level description"]


def test_parser_schema_handles_missing_description_and_epilog() -> None:
    """Verify schema behavior when description and epilog are missing."""
    layout = RecordingHelpLayout()
    commands = {
        "sample": make_command_stub(
            Function(sample),
            layout=layout,
        )
    }

    schema = ParserSchema(
        raw_description=None,
        raw_epilog=None,
        commands=commands,
        command_key="command",
        allow_args_from_file=False,
        pipe_targets=None,
        theme=layout,
        metadata={"source": "tests"},
    )

    assert schema.description is None
    assert schema.epilog is None
    assert schema.allow_args_from_file is False
    assert schema.metadata == {"source": "tests"}


def test_multi_command_schema_reports_commands_help_and_names() -> None:
    """Verify schema properties for multi-command configurations."""
    layout = RecordingHelpLayout()
    commands = {
        "sample": make_command_stub(
            Function(sample),
            layout=layout,
        ),
        "another": make_command_stub(
            Function(another),
            layout=layout,
        ),
    }

    schema = ParserSchema(
        raw_description=None,
        raw_epilog=None,
        commands=commands,
        command_key=None,
        allow_args_from_file=True,
        pipe_targets=None,
        theme=layout,
        commands_help="formatted command list",
    )

    assert schema.is_multi_command is True
    assert schema.commands_help == "formatted command list"
    assert schema.canonical_names == ("sample", "another")
    assert schema.command_key is None


def test_command_description_and_epilog_helpers() -> None:
    """Verify helper methods for command description and epilog formatting."""
    layout = RecordingHelpLayout()
    command = Command(
        obj=Function(sample),
        canonical_name="sample",
        cli_name="sample",
        aliases=(),
        raw_description="Command level",
        raw_epilog="Command epilog",
        help_layout=layout,
    )

    assert command.description == "formatted::Command level"
    assert command.epilog == "Command epilog"
    assert layout.formatted_descriptions[-1] == "Command level"

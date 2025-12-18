import pytest
from objinspect import Class, Function, Method

from interfacy.naming import DefaultFlagStrategy
from interfacy.naming.abbreviations import NoAbbreviations
from interfacy.pipe import PipeTargets
from interfacy.schema.builder import ParserSchemaBuilder
from interfacy.schema.schema import ArgumentKind, ValueShape
from tests.schema.conftest import (
    FakeParser,
    RecordingHelpLayout,
    StubTypeParser,
)


def standalone(value: int, *, verbose: bool = False) -> int:
    """Standalone command"""
    return value


class MathOps:
    """doc"""

    def __init__(self, precision: int = 2) -> None:
        self.precision = precision

    def compute_total(self, first: int, second: int) -> int:
        """calculate total"""
        return first + second

    def export_value(self, payload: str) -> str:
        return payload


class NeedsInit:
    def __init__(self, host: str, port: int = 8080) -> None:
        self.host = host
        self.port = port

    def run(self, count: int) -> int:
        return count


def test_function_cli_name_resolution(builder_parser: FakeParser) -> None:
    """Verify that function command metadata (names, aliases) is correctly resolved."""
    builder = ParserSchemaBuilder(builder_parser)
    command = builder._function_spec(
        Function(standalone),
        canonical_name="explicit",
        description="cli override",
        aliases=("alias",),
        cli_name_override="override",
    )

    assert command.canonical_name == "explicit"
    assert command.cli_name == "override"
    assert command.aliases == ("alias",)
    assert command.raw_description == "cli override"


def test_class_command_populates_epilog_and_pipe_targets(
    builder_parser: FakeParser,
) -> None:
    """Verify that class-based commands populate epilog and pipe targets correctly."""
    builder_parser.set_pipe_target("math-ops", ("result",))
    builder = ParserSchemaBuilder(builder_parser)

    command = builder._class_command(
        Class(MathOps),
        canonical_name="math-ops",
        description="class desc",
    )

    assert command.raw_epilog == "class::MathOps"
    assert command.pipe_targets is not None
    assert command.pipe_targets.targets == ("result",)
    assert command.subcommands is not None
    compute = command.subcommands["compute-total"]
    assert compute.pipe_targets is command.pipe_targets
    assert compute.raw_description == "calculate total"


def test_pipe_target_fallback_uses_original_method_name(
    builder_parser: FakeParser,
) -> None:
    """Verify that pipe target resolution falls back to original method names."""
    builder = ParserSchemaBuilder(builder_parser)
    builder_parser.set_pipe_target("math-ops", ("payload",), subcommand="compute_total")

    command = builder._class_command(
        Class(MathOps),
        canonical_name="math-ops",
    )

    assert command.subcommands is not None
    compute = command.subcommands["compute-total"]
    assert compute.pipe_targets is not None
    assert compute.pipe_targets.targets == ("payload",)


def test_method_initializer_dropped_for_bound_method(
    builder_parser: FakeParser,
) -> None:
    """Verify that initializer arguments are omitted for bound method commands."""
    builder = ParserSchemaBuilder(builder_parser)
    method = Method(NeedsInit.run, NeedsInit)

    unbound_command = builder._method_command(
        method,
        canonical_name="run",
    )
    assert unbound_command.initializer, "expected initializer for unbound method"

    bound_instance = NeedsInit(host="localhost")
    bound_command = builder._method_command(
        Method(bound_instance.run, NeedsInit),
        canonical_name="run",
    )
    assert bound_command.initializer == []
    assert [arg.display_name for arg in bound_command.parameters] == ["count"]


def test_builder_produces_schema_with_metadata_and_settings() -> None:
    """Verify that the builder produces a schema with correct metadata and settings."""
    layout = RecordingHelpLayout()
    parser = FakeParser(
        description="parser desc",
        epilog="parser tail",
        allow_args_from_file=False,
        help_layout=layout,
        metadata={"suite": "schema"},
    )
    parser.register_command(
        Function(standalone),
        canonical_name="standalone",
    )

    builder = ParserSchemaBuilder(parser)
    schema = builder.build()

    assert schema.raw_description == "parser desc"
    assert schema.raw_epilog == "parser tail"
    assert schema.allow_args_from_file is False
    assert schema.command_key == parser.COMMAND_KEY
    assert schema.metadata == {"suite": "schema"}
    assert "standalone" in schema.commands


def test_boolean_flag_behaviors(builder_parser: FakeParser) -> None:
    """Verify that boolean flag arguments are correctly configured with negative forms."""
    builder_parser.abbreviation_gen = NoAbbreviations()
    builder_parser.flag_strategy = DefaultFlagStrategy(
        style="keyword_only",
        translation_mode=builder_parser.flag_strategy.translation_mode,
    )
    builder = ParserSchemaBuilder(builder_parser)

    def flag_only(*, enable_logging: bool = False) -> None: ...

    argument = builder._function_spec(
        Function(flag_only),
        canonical_name="flag",
    ).parameters[0]

    assert argument.kind is ArgumentKind.OPTION
    assert argument.boolean_behavior is not None
    assert argument.boolean_behavior.supports_negative is True
    assert argument.boolean_behavior.negative_form == "--no-enable-logging"
    assert argument.flags == ("--enable-logging",)


def test_list_parser_requests_element_type() -> None:
    """Verify that list arguments request their element type from the type parser."""
    type_parser = StubTypeParser()

    def typed_list(values: list[int]) -> None: ...

    parser = FakeParser(type_parser=type_parser)
    builder = ParserSchemaBuilder(parser)
    argument = builder._function_spec(
        Function(typed_list),
        canonical_name="typed-list",
    ).parameters[0]

    assert argument.value_shape is ValueShape.LIST
    assert argument.parser is None  # parser returns None when type not registered
    assert argument.type is int
    assert type_parser.requests == [int]

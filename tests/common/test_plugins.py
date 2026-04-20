from __future__ import annotations

import pytest

from interfacy import Argparser
from interfacy.exceptions import DuplicatePluginError
from interfacy.plugins import (
    InterfacyPlugin,
    ParseFailureKind,
    ProvideArgumentValues,
)


class MarkerPlugin(InterfacyPlugin):
    name = "marker"

    def configure(self, parser) -> None:
        parser.metadata.setdefault("plugins", []).append(self.plugin_name)


class SchemaMetadataPlugin(InterfacyPlugin):
    name = "schema_metadata"

    def transform_schema(self, parser, schema):
        schema.metadata["transformed"] = True
        command = next(iter(schema.commands.values()))
        command.raw_description = "Plugin description"
        return schema


def _keyword_only_name(*, name: str) -> str:
    return name


class Worker:
    def ping(self) -> str:
        return "pong"


def test_constructor_and_apply_setup_register_plugins() -> None:
    parser = Argparser(
        sys_exit_enabled=False,
        print_result=False,
        plugins=[MarkerPlugin()],
    )

    assert parser.metadata["plugins"] == ["marker"]

    late_plugin = MarkerPlugin()
    with pytest.raises(DuplicatePluginError):
        parser.add_plugin(late_plugin)


def test_apply_setup_adds_plugins_after_construction() -> None:
    parser = Argparser(sys_exit_enabled=False, print_result=False)

    parser.apply_setup(plugins=[MarkerPlugin()])

    assert parser.metadata["plugins"] == ["marker"]


def test_schema_transform_plugin_updates_built_schema() -> None:
    parser = Argparser(
        sys_exit_enabled=False,
        print_result=False,
        plugins=[SchemaMetadataPlugin()],
    )
    parser.add_command(_keyword_only_name)

    schema = parser.build_parser_schema()
    command = next(iter(schema.commands.values()))

    assert schema.metadata["transformed"] is True
    assert command.description == "Plugin description"


class FillMissingValuePlugin(InterfacyPlugin):
    name = "fill_missing_value"

    def recover_parse_failure(self, parser, failure):
        if failure.kind is not ParseFailureKind.MISSING_ARGUMENTS:
            return None
        argument_ref = failure.missing_arguments[0]
        return ProvideArgumentValues(values={argument_ref: "Ada"})


class SelectSubcommandPlugin(InterfacyPlugin):
    name = "select_subcommand"

    def recover_parse_failure(self, parser, failure):
        if failure.kind is not ParseFailureKind.MISSING_SUBCOMMAND:
            return None
        return ProvideArgumentValues(subcommands={failure.command_path: "ping"})


@pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
def test_recovery_plugin_can_supply_missing_required_option(parser) -> None:
    parser.add_plugin(FillMissingValuePlugin())
    parser.add_command(_keyword_only_name)

    namespace = parser.parse_args([])

    assert namespace == {"name": "Ada"}


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_recovery_plugin_can_supply_missing_subcommand(parser) -> None:
    parser.add_plugin(SelectSubcommandPlugin())
    parser.add_command(Worker)

    namespace = parser.parse_args([])

    assert namespace == {
        "command": "ping",
        "ping": {},
    }


@pytest.mark.parametrize("parser_cls", [Argparser])
def test_constructor_plugins_run_before_parse(parser_cls) -> None:
    parser = parser_cls(
        sys_exit_enabled=False,
        print_result=False,
        plugins=[FillMissingValuePlugin()],
    )
    parser.add_command(_keyword_only_name)

    namespace = parser.parse_args([])

    assert namespace == {"name": "Ada"}

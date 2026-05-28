from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from interfacy.argparse_backend import Argparser
from interfacy.exceptions import ConfigurationError, DuplicatePluginError
from interfacy.plugins import (
    InterfacyPlugin,
    ParseFailureKind,
    ProvideArgumentValues,
)


class MarkerPlugin(InterfacyPlugin):
    name = "marker"

    def configure(self, context) -> None:
        context.parser.metadata.setdefault("plugins", []).append(self.plugin_name)


class SchemaMetadataPlugin(InterfacyPlugin):
    name = "schema_metadata"

    def transform_schema(self, context, schema):
        context.metadata["schema_backend"] = context.backend
        schema.metadata["transformed"] = True
        command = next(iter(schema.commands.values()))
        command.raw_description = "Plugin description"

        return schema


def _keyword_only_name(*, name: str) -> str:
    return name


def _two_keyword_only_values(*, first: str, second: str) -> tuple[str, str]:
    return first, second


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

    def recover_parse_failure(self, context, failure):
        if failure.kind is not ParseFailureKind.MISSING_ARGUMENTS:
            return None

        argument_ref = failure.missing_arguments[0]

        return ProvideArgumentValues(values={argument_ref: "Ada"})


class SelectSubcommandPlugin(InterfacyPlugin):
    name = "select_subcommand"

    def recover_parse_failure(self, context, failure):
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


class FillOneMissingValuePerAttemptPlugin(InterfacyPlugin):
    name = "fill_one_missing_value_per_attempt"

    def recover_parse_failure(self, context, failure):
        if failure.kind is not ParseFailureKind.MISSING_ARGUMENTS:
            return None

        argument_ref = failure.missing_arguments[0]

        return ProvideArgumentValues(values={argument_ref: argument_ref.name.upper()})


def test_parse_recovery_max_attempts_can_limit_plugin_recovery() -> None:
    parser = Argparser(
        sys_exit_enabled=False,
        print_result=False,
        parse_recovery_max_attempts=1,
        plugins=[FillOneMissingValuePerAttemptPlugin()],
    )
    parser.add_command(_two_keyword_only_values)

    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parse_recovery_max_attempts_can_allow_multi_step_plugin_recovery() -> None:
    parser = Argparser(
        sys_exit_enabled=False,
        print_result=False,
        parse_recovery_max_attempts=2,
        plugins=[FillOneMissingValuePerAttemptPlugin()],
    )
    parser.add_command(_two_keyword_only_values)

    namespace = parser.parse_args([])

    assert namespace == {"first": "FIRST", "second": "SECOND"}


class BeforeParsePlugin(InterfacyPlugin):
    name = "before_parse"

    def before_parse(self, context, args: list[str]) -> list[str]:
        context.metadata["before_backend"] = context.backend
        return ["--name", "Ada", *args]


class AfterParsePlugin(InterfacyPlugin):
    name = "after_parse"

    def after_parse(self, context, namespace: dict[str, Any]) -> dict[str, Any]:
        context.metadata["after_backend"] = context.backend
        updated = dict(namespace)
        updated["name"] = updated["name"].upper()

        return updated


@pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
def test_before_parse_plugin_can_rewrite_args(parser) -> None:
    parser.add_plugin(BeforeParsePlugin())
    parser.add_command(_keyword_only_name)

    namespace = parser.parse_args([])

    assert namespace == {"name": "Ada"}
    assert parser.metadata["before_backend"] in {"argparse", "click"}


@pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
def test_after_parse_plugin_can_rewrite_namespace(parser) -> None:
    parser.add_plugin(AfterParsePlugin())
    parser.add_command(_keyword_only_name)

    namespace = parser.parse_args(["--name", "Ada"])

    assert namespace == {"name": "ADA"}
    assert parser.metadata["after_backend"] in {"argparse", "click"}


class InvalidBeforeParsePlugin(InterfacyPlugin):
    name = "invalid_before_parse"

    def before_parse(self, context, args: list[str]) -> list[str]:
        return "bad"  # type: ignore[return-value]


class InvalidAfterParsePlugin(InterfacyPlugin):
    name = "invalid_after_parse"

    def after_parse(self, context, namespace: dict[str, Any]) -> dict[str, Any]:
        return ["bad"]  # type: ignore[return-value]


@pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
def test_before_parse_plugin_return_type_is_validated(parser) -> None:
    parser.add_plugin(InvalidBeforeParsePlugin())
    parser.add_command(_keyword_only_name)

    with pytest.raises(ConfigurationError, match="before_parse must return list"):
        parser.parse_args([])


@pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
def test_after_parse_plugin_return_type_is_validated(parser) -> None:
    parser.add_plugin(InvalidAfterParsePlugin())
    parser.add_command(_keyword_only_name)

    with pytest.raises(ConfigurationError, match="after_parse must return dict"):
        parser.parse_args(["--name", "Ada"])


class WrapExecutePlugin(InterfacyPlugin):
    def __init__(self, name: str, order: list[str]) -> None:
        self.name = name
        self.order = order

    def wrap_execute(self, context, call_next: Callable[[], Any]) -> Any:
        self.order.append(f"{self.plugin_name}:before")
        result = call_next()
        self.order.append(f"{self.plugin_name}:after")

        return f"{result}|{self.plugin_name}"


@pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
def test_wrap_execute_plugins_wrap_execution_in_registration_order(parser, capsys) -> None:
    order: list[str] = []
    parser.add_plugin(WrapExecutePlugin("outer", order))
    parser.add_plugin(WrapExecutePlugin("inner", order))

    result = parser.run(_keyword_only_name, args=["--name", "Ada"])

    assert result == "Ada|inner|outer"
    assert order == ["outer:before", "inner:before", "inner:after", "outer:after"]
    assert "Ada|inner|outer" in capsys.readouterr().out

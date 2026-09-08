from __future__ import annotations

from collections.abc import Callable
from dataclasses import fields
from typing import Any

import pytest

from interfacy import Interfacy
from interfacy.exceptions import ConfigurationError, DuplicatePluginError, UsageError
from interfacy.help import HelpContent, HelpSection
from interfacy.plugins import (
    AfterParseContext,
    BeforeParseContext,
    ConfigureContext,
    ExecuteContext,
    HelpHookContext,
    InterfacyPlugin,
    ParseFailureContext,
    ParseFailureKind,
    ProvideArgumentValues,
    SchemaTransformContext,
)
from tests.fixtures.plugins import (
    ArgparseAccessPlugin,
    ImmutableContextPlugin,
    MarkerPlugin,
    SchemaMetadataPlugin,
)


def test_phase_contexts_expose_only_phase_capabilities() -> None:
    assert {field.name for field in fields(ConfigureContext)} == {
        "backend",
        "metadata",
        "register_type_parser",
    }
    assert {field.name for field in fields(BeforeParseContext)} == {
        "backend",
        "metadata",
        "args",
    }
    assert {field.name for field in fields(SchemaTransformContext)} == {
        "backend",
        "metadata",
    }
    assert {field.name for field in fields(AfterParseContext)} == {
        "backend",
        "metadata",
        "schema",
        "args",
        "namespace",
    }
    assert {field.name for field in fields(HelpHookContext)} == {
        "backend",
        "metadata",
        "program",
        "terminal_width",
        "command_path",
        "schema",
    }
    assert {field.name for field in fields(ExecuteContext)} == {
        "backend",
        "metadata",
        "schema",
        "args",
        "namespace",
    }
    assert {field.name for field in fields(ParseFailureContext)} == {
        "backend",
        "metadata",
        "schema",
        "args",
        "namespace",
    }


def _keyword_only_name(*, name: str) -> str:
    return name


def _two_keyword_only_values(*, first: str, second: str) -> tuple[str, str]:
    return first, second


class Worker:
    def ping(self) -> str:
        return "pong"


def test_constructor_and_apply_setup_register_plugins() -> None:
    plugin = MarkerPlugin()
    parser = Interfacy(
        backend="argparse",
        print_result=False,
        plugins=[plugin],
    )

    assert plugin.configured is True

    with pytest.raises(DuplicatePluginError):
        parser.add_plugin(MarkerPlugin())


def test_apply_setup_adds_plugins_after_construction() -> None:
    parser = Interfacy(backend="argparse", print_result=False)
    plugin = MarkerPlugin()

    parser.apply_setup(plugins=[plugin])

    assert plugin.configured is True


def test_plugin_context_metadata_is_immutable() -> None:
    parser = Interfacy(
        backend="argparse",
    )
    parser.metadata["nested"] = {"values": ["original"]}

    parser.add_plugin(ImmutableContextPlugin())

    assert parser.metadata == {"nested": {"values": ["original"]}}


def test_backend_plugin_receives_explicit_adapter_context() -> None:
    plugin = ArgparseAccessPlugin()

    Interfacy(backend="argparse", plugins=[plugin])

    assert plugin.adapter_name == "ArgparseBackend"


def test_backend_plugin_rejects_incompatible_backend() -> None:
    with pytest.raises(ConfigurationError, match="requires backend 'argparse'"):
        Interfacy(backend="click", plugins=[ArgparseAccessPlugin()])


def test_schema_transform_plugin_updates_built_schema() -> None:
    parser = Interfacy(
        backend="argparse",
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


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_constructor_plugins_run_before_parse(backend: str) -> None:
    if backend == "click":
        pytest.importorskip("click")
    parser = Interfacy(
        backend=backend,
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
    parser = Interfacy(
        backend="argparse",
        print_result=False,
        parse_recovery_max_attempts=1,
        plugins=[FillOneMissingValuePerAttemptPlugin()],
    )
    parser.add_command(_two_keyword_only_values)

    with pytest.raises(UsageError):
        parser.parse_args([])


def test_parse_recovery_max_attempts_can_allow_multi_step_plugin_recovery() -> None:
    parser = Interfacy(
        backend="argparse",
        print_result=False,
        parse_recovery_max_attempts=2,
        plugins=[FillOneMissingValuePerAttemptPlugin()],
    )
    parser.add_command(_two_keyword_only_values)

    namespace = parser.parse_args([])

    assert namespace == {"first": "FIRST", "second": "SECOND"}


class BeforeParsePlugin(InterfacyPlugin):
    name = "before_parse"

    def __init__(self) -> None:
        self.backend: str | None = None

    def before_parse(
        self,
        context: BeforeParseContext,
        args: tuple[str, ...],
    ) -> tuple[str, ...]:
        self.backend = context.backend
        return ("--name", "Ada", *args)


class AfterParsePlugin(InterfacyPlugin):
    name = "after_parse"

    def __init__(self) -> None:
        self.backend: str | None = None

    def after_parse(
        self,
        context: AfterParseContext,
        namespace: dict[str, Any],
    ) -> dict[str, Any]:
        self.backend = context.backend
        updated = dict(namespace)
        updated["name"] = updated["name"].upper()

        return updated


@pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
def test_before_parse_plugin_can_rewrite_args(parser) -> None:
    plugin = BeforeParsePlugin()
    parser.add_plugin(plugin)
    parser.add_command(_keyword_only_name)

    namespace = parser.parse_args([])

    assert namespace == {"name": "Ada"}
    assert plugin.backend in {"argparse", "click"}


@pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
def test_after_parse_plugin_can_rewrite_namespace(parser) -> None:
    plugin = AfterParsePlugin()
    parser.add_plugin(plugin)
    parser.add_command(_keyword_only_name)

    namespace = parser.parse_args(["--name", "Ada"])

    assert namespace == {"name": "ADA"}
    assert plugin.backend in {"argparse", "click"}


class HelpContentPlugin(InterfacyPlugin):
    name = "help_content"

    def __init__(self) -> None:
        self.backend: str | None = None

    def transform_help(
        self,
        context: HelpHookContext,
        content: HelpContent,
    ) -> HelpContent:
        self.backend = context.backend
        assert context.command_path
        sections = tuple(section for section in content.sections if section.kind != "options")

        return HelpContent((*sections, HelpSection("epilog", "Plugin footer")))


@pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
def test_help_plugin_transforms_structured_content(parser, capsys) -> None:
    parser = Interfacy(backend=parser.backend, print_result=False)
    plugin = HelpContentPlugin()
    parser.add_plugin(plugin)

    result = parser.invoke(_keyword_only_name, args=["--help"])

    assert result is None
    assert plugin.backend in {"argparse", "click"}
    help_text = capsys.readouterr().out
    assert "options:" not in help_text.lower()
    assert "-n, --name" not in help_text
    assert help_text.rstrip().endswith("Plugin footer")


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

    with pytest.raises(
        ConfigurationError,
        match=r"before_parse.*Sequence\[str\]",
    ):
        parser.parse_args([])


@pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
def test_after_parse_plugin_return_type_is_validated(parser) -> None:
    parser.add_plugin(InvalidAfterParsePlugin())
    parser.add_command(_keyword_only_name)

    with pytest.raises(
        ConfigurationError,
        match=r"after_parse.*Mapping\[str, object\]",
    ):
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
def test_wrap_execute_plugins_wrap_execution_in_registration_order(parser) -> None:
    order: list[str] = []
    parser.add_plugin(WrapExecutePlugin("outer", order))
    parser.add_plugin(WrapExecutePlugin("inner", order))

    result = parser.invoke(_keyword_only_name, args=["--name", "Ada"])

    assert result == "Ada|inner|outer"
    assert order == ["outer:before", "inner:before", "inner:after", "outer:after"]

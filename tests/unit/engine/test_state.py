import sys
from dataclasses import dataclass
from typing import Any

import pytest

from interfacy import CommandGroup, Interfacy
from interfacy.exceptions import ConfigurationError, DuplicateCommandError
from interfacy.plugins import InterfacyPlugin


@pytest.fixture(params=["argparse", "click"])
def parser(request: pytest.FixtureRequest) -> Interfacy:
    if request.param == "click":
        pytest.importorskip("click")

    return Interfacy(backend=request.param)


def test_rebuilt_group_replaces_compiled_parser_and_executes_new_command(parser: Interfacy) -> None:
    def first() -> str:
        return "first"

    def second() -> str:
        return "second"

    group = CommandGroup("tools").add_command(first)
    parser.add_group(group)
    original = parser.build_parser()

    group.add_command(second)

    assert parser.invoke(args=["tools", "second"]) == "second"
    assert parser.build_parser() is not original


def test_schema_plugin_change_invalidates_cached_backend(parser: Interfacy) -> None:
    class DescriptionPlugin(InterfacyPlugin):
        description = "first description"

        def transform_schema(self, context, schema):
            schema.raw_description = self.description
            return schema

    def command() -> None:
        return None

    plugin = DescriptionPlugin()
    parser.add_plugin(plugin)
    parser.add_command(command)
    first = parser.build_parser()
    plugin.description = "second description"
    second = parser.build_parser()

    assert second is not first
    assert parser.get_last_schema().description == "second description"


def test_unchanged_schema_reuses_compiled_backend_after_inline_restore(parser: Interfacy) -> None:
    def persistent() -> str:
        return "persistent"

    def temporary() -> str:
        return "temporary"

    parser.add_command(persistent)
    first = parser.build_parser()
    assert parser.build_parser() is first

    assert parser.invoke(temporary, args=["temporary"]) == "temporary"

    assert parser.build_parser() is first
    assert parser.invoke(args=[]) == "persistent"


def test_cache_accepts_cyclic_user_dataclass_default(parser: Interfacy) -> None:
    @dataclass
    class Default:
        child: Any = None

    default = Default()
    default.child = default

    def command(value: Default = default) -> bool:
        return value is default

    parser.apply_setup(expand_model_params=False)
    parser.add_type_parser(Default, lambda value: default)
    parser.add_command(command)

    parser.build_parser()
    assert parser.invoke(args=[]) is True


@pytest.mark.parametrize(
    "invalid_options",
    [{"method_skips": "bad"}, {"model_expansion_max_depth": 0}, {"pipe_targets": []}],
)
def test_failed_registration_restores_names_commands_pipes_and_cache(
    parser: Interfacy,
    invalid_options: dict[str, Any],
) -> None:
    def persistent() -> str:
        return "persistent"

    def new_command() -> str:
        return "new"

    parser.add_command(persistent)
    original_parser = parser.build_parser()
    original_schema = parser.get_last_schema()
    engine = parser._engine
    names_before = engine.registry.names.snapshot()
    command_translations = dict(engine.flag_strategy.command_translator.translations)
    argument_translations = dict(engine.flag_strategy.argument_translator.translations)
    pipes_before = engine.pipes.snapshot()

    with pytest.raises(ConfigurationError):
        parser.add_command(new_command, aliases=["new-alias"], **invalid_options)

    assert engine.registry.names.snapshot() == names_before
    assert engine.flag_strategy.command_translator.translations == command_translations
    assert engine.flag_strategy.argument_translator.translations == argument_translations
    assert engine.pipes.snapshot() == pipes_before
    assert [command.canonical_name for command in parser.get_commands()] == ["persistent"]
    assert parser.get_last_schema() is original_schema
    assert parser.build_parser() is original_parser

    parser.add_command(new_command, aliases=["new-alias"])
    assert parser.invoke(args=["new-alias"]) == "new"


def test_failed_group_build_restores_translation_and_group_name(parser: Interfacy) -> None:
    def leaf() -> str:
        return "ok"

    invalid = CommandGroup("new_tools")
    invalid.add_command(leaf, name="foo_bar")
    invalid.add_command(leaf, name="foo-bar")
    engine = parser._engine
    names_before = engine.registry.names.snapshot()
    translations_before = dict(engine.flag_strategy.command_translator.translations)

    with pytest.raises(DuplicateCommandError):
        parser.add_group(invalid, aliases=["tools-alias"])

    assert parser.get_commands() == []
    assert engine.registry.names.snapshot() == names_before
    assert engine.flag_strategy.command_translator.translations == translations_before

    valid = CommandGroup("new_tools").add_command(leaf)
    parser.add_group(valid, aliases=["tools-alias"])
    assert parser.invoke(args=["tools-alias", "leaf"]) == "ok"


def test_late_ancestor_list_keeps_cli_priority_and_converts_once(
    parser: Interfacy,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    defaults = [7]
    converted: list[str] = []

    class Tool:
        def __init__(self, values: list[int] = defaults) -> None:
            self.values = values

        def show(self) -> list[int]:
            return self.values

    def convert(value: str) -> int:
        converted.append(value)
        return int(value)

    parser.add_type_parser(int, convert)
    parser.add_command(Tool, pipe_targets="values")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr("interfacy.engine.pipes.read_piped", lambda: "9")

    assert parser.invoke(args=["show", "--values", "7"]) == [7]
    assert converted.count("7") == 1

    assert parser.invoke(args=["show"]) == [9]

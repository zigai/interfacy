import pytest
from objinspect import Function

from interfacy import CommandGroup
from interfacy.schema.arguments import CommandOverrides
from interfacy.schema.builder import ParserSchemaBuilder
from interfacy.schema.sorting import HelpOptionSortRule, HelpSubcommandSortRule
from tests.unit.schema.conftest import SchemaSource


class ParentCommands:
    def inherited(self) -> str:
        return "inherited"


class Commands(ParentCommands):
    def __init__(self, prefix: str = "prefix") -> None:
        self.prefix = prefix

    def show(self) -> str:
        return self.prefix

    @staticmethod
    def static() -> str:
        return "static"

    class Nested:
        def show(self) -> str:
            return "nested"

    def _protected(self) -> str:
        return "protected"


def standalone() -> str:
    return "standalone"


def test_group_settings_inherit_without_overwriting_explicit_false(
    schema_source: SchemaSource,
) -> None:
    stored = Commands("stored")
    group = CommandGroup("root")
    group.add_command(Commands, name="inherited")
    group.add_command(
        Commands,
        name="restricted",
        include_inherited_methods=False,
        include_protected_methods=False,
        include_staticmethods=False,
    )
    group.add_command(stored, name="stored", include_inherited_methods=False)
    builder = ParserSchemaBuilder(schema_source.schema_context())

    command = builder.build_from_group(
        group,
        include_inherited_methods=True,
        include_protected_methods=True,
        include_staticmethods=True,
        help_option_sort=["name_length"],
        help_subcommand_sort=["alphabetical"],
    )

    assert command.subcommands is not None
    inherited = command.subcommands["inherited"]
    assert inherited.include_inherited_methods is None
    assert {"inherited", "protected", "static", "show"} <= set(inherited.subcommands or {})
    assert inherited.help_option_sort is None
    assert inherited.help_option_sort_effective == ["name_length"]
    assert inherited.help_subcommand_sort_effective == ["alphabetical"]

    restricted = command.subcommands["restricted"]
    assert restricted.include_inherited_methods is False
    assert restricted.include_protected_methods is False
    assert restricted.include_staticmethods is False
    assert restricted.subcommands is not None
    assert {"inherited", "protected", "static"}.isdisjoint(restricted.subcommands)
    assert "show" in restricted.subcommands
    nested = restricted.subcommands["nested"]
    assert nested.parent_path == ("root", "restricted")
    assert nested.help_option_sort_effective == ["name_length"]

    instance = command.subcommands["stored"]
    assert instance.is_instance is True
    assert instance.stored_instance is stored
    assert instance.initializer == []
    assert "inherited" not in (instance.subcommands or {})
    assert "show" in (instance.subcommands or {})


@pytest.mark.parametrize("group_entry", [False, True])
def test_public_builder_records_take_precedence_and_isolate_mutable_lists(
    schema_source: SchemaSource,
    group_entry: bool,
) -> None:
    skips = ["__init__", "skip"]
    option_sort: list[HelpOptionSortRule] = ["name_length"]
    subcommand_sort: list[HelpSubcommandSortRule] = ["alphabetical"]
    overrides = CommandOverrides(
        include_inherited_methods=False,
        include_protected_methods=True,
        include_private_methods=False,
        include_staticmethods=False,
        include_classmethods=True,
        method_skips=skips,
        expand_model_params=False,
        model_expansion_max_depth=2,
        abbreviation_scope="all_options",
        help_option_sort=option_sort,
        help_subcommand_sort=subcommand_sort,
    )
    builder = ParserSchemaBuilder(schema_source.schema_context())

    if group_entry:
        group = CommandGroup("root")
        group.add_command(standalone)
        command = builder.build_from_group(
            group,
            overrides=overrides,
            include_inherited_methods=True,
            method_skips=["ignored"],
        )
    else:
        command = builder.build_command_spec_for(
            Function(standalone),
            canonical_name="standalone",
            overrides=overrides,
            include_inherited_methods=True,
            method_skips=["ignored"],
        )

    assert command.overrides == overrides
    assert command.help_option_sort_effective == option_sort
    assert command.help_subcommand_sort_effective == subcommand_sort

    skips.append("later")
    option_sort.append("alphabetical")
    subcommand_sort.append("name_length_asc")

    assert command.method_skips == ["__init__", "skip"]
    assert command.help_option_sort == ["name_length"]
    assert command.help_subcommand_sort == ["alphabetical"]
    assert command.help_option_sort_effective == ["name_length"]
    assert command.help_subcommand_sort_effective == ["alphabetical"]

    assert command.help_option_sort is not None
    command.help_option_sort.append("choices_first")
    assert command.help_option_sort_effective == ["name_length"]

from __future__ import annotations

import argparse

import pytest

from interfacy import CommandGroup, Interfacy
from interfacy.backends.argparse.parser import ArgumentParser
from interfacy.exceptions import DuplicateCommandError
from interfacy.help import ArgparseLayout, InterfacyLayout
from interfacy.schema.nodes import Command, ParserSchema


def test_command_group_classmethod_and_staticmethod() -> None:
    """Verify classmethods and staticmethods in class commands inside CommandGroups execute cleanly."""

    class Service:
        @classmethod
        def clsmeth(cls) -> str:
            return "from_clsmeth"

        @staticmethod
        def statmeth() -> str:
            return "from_statmeth"

        def instmeth(self) -> str:
            return "from_instmeth"

    group = CommandGroup("svc")
    group.add_command(Service, include_classmethods=True, include_staticmethods=True)

    cli = Interfacy()
    cli.add_command(group)

    assert cli.invoke(args=["svc", "service", "clsmeth"]) == "from_clsmeth"
    assert cli.invoke(args=["svc", "service", "statmeth"]) == "from_statmeth"
    assert cli.invoke(args=["svc", "service", "instmeth"]) == "from_instmeth"


def test_command_group_subgroup_alias_collision() -> None:
    """Verify colliding subgroup aliases raise DuplicateCommandError during group registration."""
    root = CommandGroup("root")
    sub1 = CommandGroup("sub1", aliases=["shared"])
    sub2 = CommandGroup("sub2", aliases=["shared"])
    sub1.add_command(lambda: "pong1", name="ping")
    sub2.add_command(lambda: "pong2", name="ping")
    root.add_group(sub1)
    root.add_group(sub2)

    cli = Interfacy()
    with pytest.raises(DuplicateCommandError) as exc_info:
        cli.add_command(root)

    assert "shared" in str(exc_info.value)


def test_command_group_duplicate_alias_names_alias() -> None:
    """Verify duplicate alias on command inside CommandGroup reports the duplicated alias token."""
    group = CommandGroup("g")

    def my_cmd() -> None:
        pass

    group.add_command(my_cmd, aliases=["alias1", "alias1"])

    cli = Interfacy()
    with pytest.raises(DuplicateCommandError) as exc_info:
        cli.add_command(group)

    assert "alias1" in str(exc_info.value)


def test_group_function_commands_render_kebab_case_names() -> None:
    ops = CommandGroup("ops")

    def cache_prune() -> None:
        """Prune cache keys."""

    ops.add_command(cache_prune)
    parser = Interfacy(backend="argparse", help_layout=ArgparseLayout(), print_result=False)
    parser.add_command(ops)

    root = parser.build_parser()
    action = next(a for a in root._actions if isinstance(a, argparse._SubParsersAction))
    ops_parser = action.choices["ops"]
    help_text = ops_parser.format_help()

    assert "cache-prune" in help_text
    assert "cache_prune" not in help_text


def test_grouped_root_help_omits_help_option_when_add_help_disabled() -> None:
    layout = ArgparseLayout()
    parser = ArgumentParser(prog="manual", help_layout=layout, add_help=False)
    parser.set_schema(
        ParserSchema(
            raw_description=None,
            raw_epilog=None,
            commands={
                "clone": Command(
                    obj=None,
                    canonical_name="clone",
                    cli_name="clone",
                    aliases=(),
                    raw_description="Clone a repository.",
                    help_group="setup",
                ),
                "status": Command(
                    obj=None,
                    canonical_name="status",
                    cli_name="status",
                    aliases=(),
                    raw_description="Show current status.",
                ),
            },
            command_key=None,
            allow_args_from_file=False,
            pipe_targets=None,
        )
    )

    help_text = parser.format_help()

    assert "--help" not in help_text
    assert "options:" not in help_text


def test_grouped_subcommand_help_preserves_custom_help_flag_prefix() -> None:
    layout = ArgparseLayout()
    parser = ArgumentParser(prog="manual ops", help_layout=layout, prefix_chars="+")
    parser.set_schema_command(
        Command(
            obj=None,
            canonical_name="ops",
            cli_name="ops",
            aliases=(),
            raw_description="Operations.",
            subcommands={
                "clone": Command(
                    obj=None,
                    canonical_name="clone",
                    cli_name="clone",
                    aliases=(),
                    raw_description="Clone a repository.",
                    help_group="setup",
                ),
                "status": Command(
                    obj=None,
                    canonical_name="status",
                    cli_name="status",
                    aliases=(),
                    raw_description="Show current status.",
                ),
            },
            is_leaf=False,
        )
    )

    help_text = parser.format_help()

    assert "[++help]" in help_text
    assert "  ++help" in help_text
    assert "--help" not in help_text


def test_interfacy_layout_usage_subcommand_choices_exclude_aliases() -> None:
    ops = CommandGroup("ops")
    ops.add_command(lambda: None, name="cache_prune", aliases=("prune",))

    parser = Interfacy(backend="argparse", help_layout=InterfacyLayout(), print_result=False)
    parser.add_command(ops)

    root = parser.build_parser()
    action = next(a for a in root._actions if isinstance(a, argparse._SubParsersAction))
    ops_parser = action.choices["ops"]
    help_text = ops_parser.format_help()

    assert "{cache-prune}" in help_text
    assert "{cache-prune,prune}" not in help_text


def test_argparse_layout_group_usage_includes_subcommand_choices() -> None:
    ops = CommandGroup("ops")
    ops.add_command(lambda: None, name="cache_prune")

    parser = Interfacy(backend="argparse", help_layout=ArgparseLayout(), print_result=False)
    parser.add_command(ops)
    root = parser.build_parser()
    action = next(a for a in root._actions if isinstance(a, argparse._SubParsersAction))
    ops_parser = action.choices["ops"]
    help_text = ops_parser.format_help()

    assert "{cache-prune}" in help_text

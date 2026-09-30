from __future__ import annotations

import pytest

from interfacy import CommandGroup, Interfacy
from interfacy.exceptions import DuplicateCommandError


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

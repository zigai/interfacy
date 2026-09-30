import pytest

from interfacy import CommandGroup, Interfacy
from interfacy.exceptions import UsageError


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


def test_group_settings_inherit_without_overwriting_explicit_false() -> None:
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
    parser = Interfacy(
        include_inherited_methods=True,
        include_protected_methods=True,
        include_staticmethods=True,
    )
    parser.add_command(group)

    assert parser.invoke(args=["root", "inherited", "inherited"]) == "inherited"
    assert parser.invoke(args=["root", "inherited", "protected"]) == "protected"
    assert parser.invoke(args=["root", "inherited", "static"]) == "static"
    assert parser.invoke(args=["root", "restricted", "show"]) == "prefix"
    assert parser.invoke(args=["root", "restricted", "nested", "show"]) == "nested"
    assert parser.invoke(args=["root", "stored", "show"]) == "stored"

    for args in (
        ["root", "restricted", "inherited"],
        ["root", "restricted", "protected"],
        ["root", "restricted", "static"],
        ["root", "stored", "inherited"],
    ):
        with pytest.raises(UsageError):
            parser.invoke(args=args)

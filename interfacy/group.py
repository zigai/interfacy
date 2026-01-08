from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class CommandEntry:
    """Internal representation of a command added to a group."""

    obj: Callable | type | object
    name: str
    description: str | None
    aliases: tuple[str, ...]
    is_instance: bool


class CommandGroup:
    """
    A command group for building nested CLI hierarchies.

    Supports manual construction of deeply nested command structures:
    - add_command(function) -> leaf command
    - add_command(class) -> subgroup with methods as commands
    - add_command(instance) -> subgroup with methods as commands (no __init__ args)
    - add_group(CommandGroup) -> nested subgroup
    """

    def __init__(
        self,
        name: str,
        description: str | None = None,
        aliases: tuple[str, ...] | list[str] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.aliases = tuple(aliases) if aliases else ()
        self._commands: dict[str, CommandEntry] = {}
        self._subgroups: dict[str, CommandGroup] = {}
        self._group_args_source: type | Callable | None = None

    def add_command(
        self,
        command: Callable | type | object,
        name: str | None = None,
        description: str | None = None,
        aliases: tuple[str, ...] | list[str] | None = None,
    ) -> CommandGroup:
        """
        Add a command to this group.

        Args:
            command: Function, class, or class instance to add.
            name: Override the command name (defaults to function/class name).
            description: Override the description.
            aliases: Alternative names for this command.
        """
        is_instance = False
        cmd_name: str

        if isinstance(command, type):
            cmd_name = name or command.__name__
        elif callable(command):
            cmd_name = name or command.__name__
        else:
            is_instance = True
            cmd_name = name or type(command).__name__

        if description is None:
            if hasattr(command, "__doc__") and command.__doc__:
                description = command.__doc__.split("\n")[0].strip()

        entry = CommandEntry(
            obj=command,
            name=cmd_name,
            description=description,
            aliases=tuple(aliases) if aliases else (),
            is_instance=is_instance,
        )
        self._commands[cmd_name] = entry
        return self

    def add_group(
        self,
        group: CommandGroup,
        name: str | None = None,
    ) -> CommandGroup:
        """
        Add a nested subgroup.

        Args:
            group: The CommandGroup to add as a subgroup.
            name: Override the subgroup name.
        """
        group_name = name or group.name
        self._subgroups[group_name] = group
        return self

    def with_args(self, source: type | Callable) -> CommandGroup:
        """
        Set group-level arguments from a class __init__ or function signature.

        Args:
            source: A class (uses __init__ params) or callable (uses signature).
        """
        self._group_args_source = source
        return self

    @property
    def commands(self) -> dict[str, CommandEntry]:
        """Return a copy of the commands dictionary."""
        return dict(self._commands)

    @property
    def subgroups(self) -> dict[str, CommandGroup]:
        """Return a copy of the subgroups dictionary."""
        return dict(self._subgroups)

    @property
    def has_subgroups(self) -> bool:
        return len(self._subgroups) > 0

    @property
    def has_commands(self) -> bool:
        return len(self._commands) > 0

    @property
    def is_empty(self) -> bool:
        return not self.has_commands and not self.has_subgroups

    def __repr__(self) -> str:
        return (
            f"CommandGroup(name={self.name!r}, "
            f"commands={list(self._commands.keys())}, "
            f"subgroups={list(self._subgroups.keys())})"
        )


__all__ = ["CommandGroup", "CommandEntry"]

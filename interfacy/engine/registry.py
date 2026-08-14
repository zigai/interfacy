from __future__ import annotations

from collections.abc import Sequence

from interfacy.exceptions import InvalidCommandError
from interfacy.naming import CommandNameRegistry
from interfacy.naming.name_mapping import NameMapping
from interfacy.schema.schema import Command

NameRegistrySnapshot = tuple[set[str], dict[str, str]]


class CommandRegistry:
    def __init__(self, translator: NameMapping) -> None:
        self.names: CommandNameRegistry = CommandNameRegistry(translator)
        self.commands: dict[str, Command] = {}
        self.generation = 0

    def register_name(
        self,
        *,
        default_name: str,
        explicit_name: str | None,
        aliases: Sequence[str] | None,
    ) -> tuple[str, tuple[str, ...]]:
        return self.names.register(
            default_name=default_name,
            explicit_name=explicit_name,
            aliases=aliases,
        )

    def add(self, command: Command) -> None:
        self.commands[command.canonical_name] = command
        self.generation += 1

    def all(self) -> list[Command]:
        return list(self.commands.values())

    def get_by_cli_name(self, cli_name: str) -> Command:
        canonical_name = self.names.canonical_for(cli_name)
        if canonical_name is None:
            raise InvalidCommandError(cli_name)

        return self.commands[canonical_name]

    def snapshot(self) -> tuple[dict[str, Command], NameRegistrySnapshot, int]:
        return dict(self.commands), self.names.snapshot(), self.generation

    def restore(
        self,
        commands: dict[str, Command],
        names: NameRegistrySnapshot,
        generation: int | None = None,
    ) -> None:
        self.commands = dict(commands)
        self.names.restore(names)
        self.generation = self.generation + 1 if generation is None else generation


__all__ = ["CommandRegistry"]

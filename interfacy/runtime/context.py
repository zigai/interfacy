from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from objinspect import Parameter
from strto import StrToTypeParser

from interfacy.naming.name_mapping import NameMapping
from interfacy.pipe import PipeTargets
from interfacy.schema.schema import Command, ParserSchema


@dataclass(frozen=True)
class ExecutionContext:
    commands: dict[str, Command]
    argument_names: NameMapping
    command_names: NameMapping
    type_parser: StrToTypeParser
    schema: ParserSchema | None
    read_piped_input: Callable[[], str | None]
    resolve_pipe_targets: Callable[[Command, str | None], PipeTargets | None]
    parameters_for: Callable[[Command, str | None], dict[str, Parameter]]
    cli_supplied_parameters_for: Callable[[Command, str | None], set[str] | None]
    command_key: str = "command"

    def get_commands(self) -> list[Command]:
        return list(self.commands.values())

    def get_command_by_cli_name(self, name: str) -> Command:
        for command in self.commands.values():
            if command.cli_name == name or name in command.aliases:
                return command

        raise KeyError(name)


__all__ = ["ExecutionContext"]

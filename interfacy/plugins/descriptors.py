from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from interfacy.plugins.freeze import freeze
from interfacy.schema.model import Argument, Command, ParserSchema


@dataclass(slots=True, unsafe_hash=True)
class ArgumentDescriptor:
    """Backend-neutral description of a schema argument."""

    command_path: tuple[str, ...]
    name: str
    display_name: str
    kind: str
    value_shape: str
    flags: tuple[str, ...]
    required: bool
    type: type[Any] | None
    choices: tuple[Any, ...] | None = field(default=None, compare=False, hash=False)
    metadata: Mapping[str, Any] = field(
        default_factory=dict,
        compare=False,
        hash=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        self.command_path = tuple(self.command_path)
        self.flags = tuple(self.flags)
        self.choices = freeze(self.choices)
        self.metadata = freeze(self.metadata)

    @classmethod
    def from_argument(
        cls,
        command_path: tuple[str, ...],
        argument: Argument,
    ) -> ArgumentDescriptor:
        """Describe a schema argument owned by the command at ``command_path``."""
        return cls(
            command_path=command_path,
            name=argument.name,
            display_name=argument.display_name,
            kind=argument.kind.value,
            value_shape=argument.value_shape.value,
            flags=tuple(argument.flags),
            required=argument.required,
            type=argument.type,
            choices=tuple(argument.choices) if argument.choices else None,
            metadata=argument.metadata,
        )


@dataclass(slots=True)
class SchemaDescriptor:
    """Schema snapshot shared by plugin phases."""

    description: str | None
    epilog: str | None
    command_paths: tuple[tuple[str, ...], ...]
    arguments: tuple[ArgumentDescriptor, ...]
    metadata: Mapping[str, Any] = field(
        default_factory=dict,
        compare=False,
        hash=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        self.command_paths = tuple(tuple(path) for path in self.command_paths)
        self.arguments = tuple(self.arguments)
        self.metadata = freeze(self.metadata)

    @classmethod
    def from_schema(cls, schema: ParserSchema) -> SchemaDescriptor:
        """Describe every command path and argument in ``schema``."""
        paths: list[tuple[str, ...]] = []
        arguments: list[ArgumentDescriptor] = []

        def visit(command: Command, path: tuple[str, ...]) -> None:
            paths.append(path)
            arguments.extend(
                ArgumentDescriptor.from_argument(path, argument)
                for argument in (*command.initializer, *command.parameters)
            )

            for child in (command.subcommands or {}).values():
                visit(child, (*path, child.canonical_name))

        for command in schema.commands.values():
            visit(command, (command.canonical_name,))

        return cls(
            description=schema.description,
            epilog=schema.epilog,
            command_paths=tuple(paths),
            arguments=tuple(arguments),
            metadata=schema.metadata,
        )


__all__ = ["ArgumentDescriptor", "SchemaDescriptor"]

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property
from typing import Any, Literal

from objinspect import Class, Function, Method

from interfacy.appearance.layout import HelpLayout
from interfacy.pipe import PipeTargets

CommandType = Literal["function", "method", "class", "group", "instance"]
MODEL_DEFAULT_UNSET: object = object()


class ArgumentKind(str, Enum):
    POSITIONAL = "positional"
    OPTION = "option"


class ValueShape(str, Enum):
    SINGLE = "single"
    LIST = "list"
    TUPLE = "tuple"
    FLAG = "flag"


@dataclass
class BooleanBehavior:
    supports_negative: bool
    negative_form: str | None
    default: bool | None


@dataclass
class Argument:
    name: str
    display_name: str
    kind: ArgumentKind
    value_shape: ValueShape
    flags: tuple[str, ...]
    required: bool
    default: Any
    help: str | None
    type: type[Any] | None
    parser: Callable[[str], Any] | None
    metavar: str | None = None
    nargs: str | int | None = None
    boolean_behavior: BooleanBehavior | None = None
    choices: Sequence[Any] | None = None
    accepts_stdin: bool = False
    pipe_required: bool = False
    tuple_element_parsers: tuple[Callable[[str], Any], ...] | None = None
    is_expanded_from: str | None = None
    expansion_path: tuple[str, ...] = ()
    original_model_type: type | None = None
    parent_is_optional: bool = False
    model_default: Any = MODEL_DEFAULT_UNSET


@dataclass
class Command:
    obj: Class | Function | Method | None
    canonical_name: str
    cli_name: str
    aliases: tuple[str, ...]
    raw_description: str | None
    help_layout: HelpLayout | None = None
    pipe_targets: PipeTargets | None = None
    parameters: list[Argument] = field(default_factory=list)
    initializer: list[Argument] = field(default_factory=list)
    subcommands: dict[str, Command] | None = None
    raw_epilog: str | None = None
    command_type: CommandType = "function"
    is_leaf: bool = True
    is_instance: bool = False
    parent_path: tuple[str, ...] = ()
    stored_instance: object | None = None

    @cached_property
    def description(self) -> str | None:
        if self.raw_description is None:
            return None
        if self.help_layout is None:
            return self.raw_description
        return self.help_layout.format_description(self.raw_description)

    @cached_property
    def epilog(self) -> str | None:
        return self.raw_epilog


@dataclass
class ParserSchema:
    raw_description: str | None
    raw_epilog: str | None
    commands: dict[str, Command]
    command_key: str | None
    allow_args_from_file: bool
    pipe_targets: PipeTargets | None
    theme: HelpLayout
    commands_help: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @cached_property
    def description(self) -> str | None:
        if self.raw_description is None:
            return None
        return self.theme.format_description(self.raw_description)

    @cached_property
    def epilog(self) -> str | None:
        if self.raw_epilog is None:
            return None
        return self.theme.format_description(self.raw_epilog)

    @property
    def is_multi_command(self) -> bool:
        return len(self.commands) > 1

    def get_command(self, canonical_name: str) -> Command:
        return self.commands[canonical_name]

    @property
    def canonical_names(self) -> Sequence[str]:
        return tuple(self.commands.keys())


__all__ = [
    "ArgumentKind",
    "Argument",
    "BooleanBehavior",
    "Command",
    "CommandType",
    "MODEL_DEFAULT_UNSET",
    "ParserSchema",
    "ValueShape",
]

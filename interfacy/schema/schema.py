from __future__ import annotations

import builtins
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
    """Classification of how a CLI argument is provided."""

    POSITIONAL = "positional"
    OPTION = "option"


class ValueShape(str, Enum):
    """Shape of a parameter's parsed value."""

    SINGLE = "single"
    LIST = "list"
    TUPLE = "tuple"
    FLAG = "flag"


@dataclass
class BooleanBehavior:
    """
    Metadata for boolean flags and their defaults.

    Attributes:
        supports_negative (bool): Whether a negative form is generated.
        negative_form (str | None): Negative flag form (e.g., "--no-flag") if any.
        default (bool | str | None): Effective default value for the flag.
            Can be argparse.SUPPRESS (a str sentinel) to suppress the default.
    """

    supports_negative: bool
    negative_form: str | None
    default: bool | str | None


@dataclass
class Argument:
    """
    Schema entry describing a single CLI argument.

    Attributes:
        name (str): Canonical parameter name.
        display_name (str): CLI-facing name or path.
        kind (ArgumentKind): Whether the argument is positional or optional.
        value_shape (ValueShape): Expected value shape for parsing.
        flags (tuple[str, ...]): CLI flags or positional name display.
        required (bool): Whether the argument must be provided.
        default (Any): Default value or argparse sentinel.
        help (str | None): Help text for display.
        type (type[Any] | None): Parsed element type when applicable.
        parser (Callable[[str], Any] | None): Parser for converting raw strings.
        metavar (str | None): Custom metavar for help display.
        nargs (str | int | None): Argparse nargs specifier.
        boolean_behavior (BooleanBehavior | None): Boolean flag behavior details.
        choices (Sequence[Any] | None): Allowed values, if any.
        accepts_stdin (bool): Whether stdin can supply this value.
        pipe_required (bool): Whether stdin is required for this value.
        tuple_element_parsers (tuple[Callable[[str], Any], ...] | None): Per-element parsers.
        is_expanded_from (str | None): Root model field name if expanded.
        expansion_path (tuple[str, ...]): Nested path for expanded model fields.
        original_model_type (type | None): Model type expanded into flags.
        parent_is_optional (bool): Whether an ancestor model is optional.
        model_default (Any): Default model instance or sentinel.
    """

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
    original_model_type: builtins.type[Any] | None = None
    parent_is_optional: bool = False
    model_default: Any = MODEL_DEFAULT_UNSET


@dataclass
class Command:
    """
    Schema entry describing a CLI command and its parameters.

    Attributes:
        obj (Class | Function | Method | None): Inspected callable backing the command.
        canonical_name (str): Canonical command name.
        cli_name (str): CLI-facing command name.
        aliases (tuple[str, ...]): Alternative CLI names.
        raw_description (str | None): Raw docstring description.
        help_layout (HelpLayout | None): Help layout used for formatting.
        pipe_targets (PipeTargets | None): Pipe target configuration for stdin.
        parameters (list[Argument]): Argument specs for command parameters.
        initializer (list[Argument]): Argument specs for class initialization.
        subcommands (dict[str, Command] | None): Nested subcommands, if any.
        raw_epilog (str | None): Raw epilog text for help output.
        command_type (CommandType): Command category.
        is_leaf (bool): Whether this command has no subcommands.
        is_instance (bool): Whether the command comes from a stored instance.
        parent_path (tuple[str, ...]): Command path for nested groups.
        stored_instance (object | None): Stored instance for instance commands.
    """

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
        """Return the formatted description for help output."""
        if self.raw_description is None:
            return None
        if self.help_layout is None:
            return self.raw_description
        return self.help_layout.format_description(self.raw_description)

    @cached_property
    def epilog(self) -> str | None:
        """Return the formatted epilog for help output."""
        return self.raw_epilog


@dataclass
class ParserSchema:
    """
    Schema container for a complete CLI parser.

    Attributes:
        raw_description (str | None): Raw description string.
        raw_epilog (str | None): Raw epilog string.
        commands (dict[str, Command]): Command definitions keyed by canonical name.
        command_key (str | None): Key used for command selection in parsed args.
        allow_args_from_file (bool): Whether args can be read from files.
        pipe_targets (PipeTargets | None): Default pipe target configuration.
        theme (HelpLayout): Help layout for formatting.
        commands_help (str | None): Pre-rendered command listing help.
        metadata (dict[str, Any]): Additional parser metadata.
    """

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
        """Return the formatted parser description."""
        if self.raw_description is None:
            return None
        return self.theme.format_description(self.raw_description)

    @cached_property
    def epilog(self) -> str | None:
        """Return the formatted parser epilog."""
        if self.raw_epilog is None:
            return None
        return self.theme.format_description(self.raw_epilog)

    @property
    def is_multi_command(self) -> bool:
        """Whether the schema contains multiple top-level commands."""
        return len(self.commands) > 1

    def get_command(self, canonical_name: str) -> Command:
        """
        Return the command definition for a canonical name.

        Args:
            canonical_name (str): Canonical command name.
        """
        return self.commands[canonical_name]

    @property
    def canonical_names(self) -> Sequence[str]:
        """Return the canonical command names in schema order."""
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

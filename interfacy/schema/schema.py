from __future__ import annotations

import builtins
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from interfacy.schema.arguments import CommandOverrides

from objinspect import Class, Function, Method

from interfacy.executable_flag import ExecutableFlag
from interfacy.parameters import BooleanMode, Param
from interfacy.pipe import PipeTargets
from interfacy.schema.sorting import HelpOptionSortRule, HelpSubcommandSortRule
from interfacy.schema.value_plan import ArgumentValue, ValueCardinality

CommandType = Literal["function", "method", "class", "group", "instance"]
MODEL_DEFAULT_UNSET: Any = object()


@dataclass(frozen=True)
class ArgumentDefault:
    """Effective argument default and its parse and help-display policies."""

    is_set: bool
    value: Any
    suppress_parse_default: bool
    suppress_help_default: bool

    def __post_init__(self) -> None:
        if not isinstance(self.is_set, bool):
            raise TypeError("is_set must be a boolean")
        if not isinstance(self.suppress_parse_default, bool):
            raise TypeError("suppress_parse_default must be a boolean")
        if not isinstance(self.suppress_help_default, bool):
            raise TypeError("suppress_help_default must be a boolean")
        if self.is_set:
            return
        if self.value is not None:
            raise ValueError("an absent argument default cannot carry a value")
        if not self.suppress_parse_default or not self.suppress_help_default:
            raise ValueError("an absent argument default must be suppressed")

    @classmethod
    def absent(cls) -> ArgumentDefault:
        return cls(
            is_set=False,
            value=None,
            suppress_parse_default=True,
            suppress_help_default=True,
        )

    @classmethod
    def present(
        cls,
        value: Any,
        *,
        suppress_parse_default: bool = False,
        suppress_help_default: bool = False,
    ) -> ArgumentDefault:
        return cls(
            is_set=True,
            value=value,
            suppress_parse_default=suppress_parse_default,
            suppress_help_default=suppress_help_default,
        )

    @property
    def applies_during_parse(self) -> bool:
        return self.is_set and not self.suppress_parse_default

    @property
    def appears_in_help(self) -> bool:
        return self.is_set and not self.suppress_help_default


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
    """Metadata for boolean flag spellings and mode."""

    positive_flags: tuple[str, ...]
    negative_flags: tuple[str, ...]
    default: bool | str | None
    mode: BooleanMode = BooleanMode.DUAL


@dataclass
class Argument:
    """Backend-neutral schema entry describing a single CLI argument."""

    name: str
    display_name: str
    kind: ArgumentKind
    value_shape: ValueShape
    flags: tuple[str, ...]
    required: bool
    cardinality: ValueCardinality
    argument_default: ArgumentDefault
    help: str | None
    type: type[Any] | None
    parser: Callable[[str], Any] | None
    metavar: str | None = None
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
    is_help_action: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    value_plan: ArgumentValue | None = None


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
        help_group (str | None): Optional help-only grouping label for command listings.
        pipe_targets (PipeTargets | None): Pipe target configuration for stdin.
        parameters (list[Argument]): Argument specs for command parameters.
        initializer (list[Argument]): Argument specs for class initialization.
        subcommands (dict[str, Command] | None): Nested subcommands, if any.
        executable_flags (list[ExecutableFlag]): Zero-argument executable flags.
        raw_epilog (str | None): Raw epilog text for help output.
        command_type (CommandType): Command category.
        is_leaf (bool): Whether this command has no subcommands.
        is_instance (bool): Whether the command comes from a stored instance.
        parent_path (tuple[str, ...]): Command path for nested groups.
        stored_instance (object | None): Stored instance for instance commands.
        parameter_settings (dict[str, Param]): Per-parameter CLI setting overrides.
    """

    obj: Class | Function | Method | None
    canonical_name: str
    cli_name: str
    aliases: tuple[str, ...]
    raw_description: str | None
    help_group: str | None = None
    pipe_targets: PipeTargets | None = None
    parameters: list[Argument] = field(default_factory=list)
    initializer: list[Argument] = field(default_factory=list)
    subcommands: dict[str, Command] | None = None
    executable_flags: list[ExecutableFlag] = field(default_factory=list)
    raw_epilog: str | None = None
    command_type: CommandType = "function"
    is_leaf: bool = True
    is_instance: bool = False
    parent_path: tuple[str, ...] = ()
    stored_instance: Any | None = None
    include_inherited_methods: bool | None = None
    include_protected_methods: bool | None = None
    include_private_methods: bool | None = None
    include_staticmethods: bool | None = None
    group_source: Any | None = None
    include_classmethods: bool | None = None
    method_skips: list[str] | None = None
    expand_model_params: bool | None = None
    model_expansion_max_depth: int | None = None
    abbreviation_scope: str | None = None
    help_option_sort: list[HelpOptionSortRule] | None = None
    help_subcommand_sort: list[HelpSubcommandSortRule] | None = None
    help_option_sort_effective: list[HelpOptionSortRule] | None = None
    help_subcommand_sort_effective: list[HelpSubcommandSortRule] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    parameter_settings: dict[str, Param] = field(default_factory=dict)

    @property
    def description(self) -> str | None:
        return self.raw_description

    @property
    def epilog(self) -> str | None:
        return self.raw_epilog

    @property
    def overrides(self) -> CommandOverrides:
        from interfacy.schema.arguments import CommandOverrides

        return CommandOverrides(
            include_inherited_methods=self.include_inherited_methods,
            include_protected_methods=self.include_protected_methods,
            include_private_methods=self.include_private_methods,
            include_staticmethods=self.include_staticmethods,
            include_classmethods=self.include_classmethods,
            method_skips=self.method_skips,
            expand_model_params=self.expand_model_params,
            model_expansion_max_depth=self.model_expansion_max_depth,
            abbreviation_scope=self.abbreviation_scope,
            help_option_sort=self.help_option_sort,
            help_subcommand_sort=self.help_subcommand_sort,
        )


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
        metadata (dict[str, Any]): Additional parser metadata.
        executable_flags (list[ExecutableFlag]): Parser-root executable flags.
        help_option_sort_effective (list[HelpOptionSortRule] | None): Effective root option sort.
        help_subcommand_sort_effective (list[HelpSubcommandSortRule] | None): Effective root subcommand sort.
        help_flags (tuple[str, ...]): Help flag aliases for synthetic help rows.
    """

    raw_description: str | None
    raw_epilog: str | None
    commands: dict[str, Command]
    command_key: str | None
    allow_args_from_file: bool
    pipe_targets: PipeTargets | None
    metadata: dict[str, Any] = field(default_factory=dict)
    executable_flags: list[ExecutableFlag] = field(default_factory=list)
    help_option_sort_effective: list[HelpOptionSortRule] | None = None
    help_subcommand_sort_effective: list[HelpSubcommandSortRule] | None = None
    help_flags: tuple[str, ...] = ("--help",)

    @property
    def description(self) -> str | None:
        return self.raw_description

    @property
    def epilog(self) -> str | None:
        return self.raw_epilog

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


def find_command(
    commands: Sequence[Command] | dict[str, Command],
    name_or_alias: str,
) -> Command | None:
    """Find a command matching canonical name, cli_name, or any registered alias."""
    candidates = commands.values() if isinstance(commands, dict) else commands
    for cmd in candidates:
        if name_or_alias in (cmd.canonical_name, cmd.cli_name, *cmd.aliases):
            return cmd

    return None


def finalize_schema(schema: ParserSchema) -> ParserSchema:
    """Validate a transformed schema at the boundary before backend compilation."""
    if not isinstance(schema, ParserSchema):
        raise TypeError("schema transformations must return a ParserSchema")

    _validate_command_mapping(schema.commands, path=(), active_command_ids=set(), root=True)

    return schema


def _validate_command_mapping(
    commands: dict[str, Command],
    *,
    path: tuple[str, ...],
    active_command_ids: set[int],
    root: bool,
) -> None:
    if not isinstance(commands, dict):
        raise TypeError("schema command collections must be dictionaries")

    for key, command in commands.items():
        if not isinstance(key, str):
            raise TypeError("schema command keys must be strings")

        if not isinstance(command, Command):
            command_path = " ".join((*path, key))
            raise TypeError(f"schema command {command_path!r} must be a Command")

        expected_key = command.canonical_name if root else command.cli_name
        if key != expected_key:
            command_path = " ".join((*path, key))
            raise ValueError(
                f"schema command key {command_path!r} does not match expected name {expected_key!r}"
            )
        if not command.cli_name:
            command_path = " ".join((*path, key))
            raise ValueError(f"schema command {command_path!r} must have a CLI name")
        if command.subcommands is None:
            continue

        command_id = id(command)
        if command_id in active_command_ids:
            command_path = " ".join((*path, key))
            raise ValueError(f"schema command {command_path!r} contains a cycle")

        active_command_ids.add(command_id)
        _validate_command_mapping(
            command.subcommands,
            path=(*path, key),
            active_command_ids=active_command_ids,
            root=False,
        )
        active_command_ids.remove(command_id)


__all__ = [
    "MODEL_DEFAULT_UNSET",
    "Argument",
    "ArgumentDefault",
    "ArgumentKind",
    "BooleanBehavior",
    "BooleanMode",
    "Command",
    "CommandType",
    "ExecutableFlag",
    "ParserSchema",
    "ValueCardinality",
    "ValueShape",
    "finalize_schema",
    "find_command",
]

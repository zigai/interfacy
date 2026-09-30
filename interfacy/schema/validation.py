from __future__ import annotations

from collections.abc import Sequence

from interfacy.declarations.executable_flags import ExecutableFlag, executable_flag_tokens
from interfacy.exceptions import ConfigurationError, ReservedFlagError
from interfacy.schema.model import Argument, ArgumentKind, Command, ParserSchema, ValueShape


def validate_parser_schema(schema: ParserSchema) -> ParserSchema:
    """
    Validate a transformed schema at the boundary before backend compilation.

    Args:
        schema (ParserSchema): Schema returned by the transform phase.

    Raises:
        TypeError: The schema or one of its commands has the wrong type.
        ValueError: A command key, CLI name, or nesting is inconsistent.
    """
    if not isinstance(schema, ParserSchema):
        raise TypeError("schema transformations must return a ParserSchema")

    validate_command_mapping(schema.commands, path=(), active_command_ids=set(), root=True)

    return schema


def validate_command_mapping(
    commands: dict[str, Command],
    *,
    path: tuple[str, ...],
    active_command_ids: set[int],
    root: bool,
) -> None:
    """
    Validate a command mapping and its nested subcommands.

    Args:
        commands (dict[str, Command]): Commands keyed by canonical (root) or CLI name.
        path (tuple[str, ...]): Command keys leading to this mapping.
        active_command_ids (set[int]): Identities of commands on the current path.
        root (bool): Whether the mapping is the schema's top-level command mapping.

    Raises:
        TypeError: A key or command has the wrong type.
        ValueError: A key mismatches its command, a CLI name is empty, or commands cycle.
    """
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
        validate_command_mapping(
            command.subcommands,
            path=(*path, key),
            active_command_ids=active_command_ids,
            root=False,
        )
        active_command_ids.remove(command_id)


def positional_arguments(arguments: Sequence[Argument]) -> list[Argument]:
    """
    Return the positional arguments in declaration order.

    Args:
        arguments (Sequence[Argument]): Arguments to filter.
    """
    return [argument for argument in arguments if argument.kind is ArgumentKind.POSITIONAL]


def argument_option_strings(arguments: Sequence[Argument]) -> set[str]:
    """
    Return the dash-prefixed option strings used by option arguments.

    Args:
        arguments (Sequence[Argument]): Arguments to inspect.
    """
    option_strings: set[str] = set()
    for argument in arguments:
        if argument.kind is not ArgumentKind.OPTION:
            continue

        option_strings.update(flag for flag in argument.flags if flag.startswith("-"))

    return option_strings


def command_option_strings(command: Command) -> set[str]:
    """
    Return every option token a command claims, including its executable flags.

    Args:
        command (Command): Command to inspect.
    """
    option_strings = argument_option_strings([*command.initializer, *command.parameters])
    option_strings.update(executable_flag_tokens(command.executable_flags))

    return option_strings


def validate_positional_order(arguments: Sequence[Argument], *, owner: str) -> None:
    """
    Reject optional positionals followed by required or list positionals.

    Args:
        arguments (Sequence[Argument]): Arguments in declaration order.
        owner (str): Command name used in error messages.

    Raises:
        ConfigurationError: An optional positional precedes an ambiguous positional.
    """
    optional_argument: Argument | None = None
    for argument in positional_arguments(arguments):
        if optional_argument is not None and (
            optional_argument.value_shape is ValueShape.LIST or argument.required
        ):
            raise ConfigurationError(
                f"Optional positional parameter '{optional_argument.display_name}' in "
                f"'{owner}' cannot appear before positional parameter "
                f"'{argument.display_name}'"
            )

        if not argument.required:
            optional_argument = argument


def validate_optional_initializer_positionals(
    *,
    owner: str,
    initializer: Sequence[Argument],
    subcommands: dict[str, Command],
) -> None:
    """
    Reject optional initializer positionals on commands that have subcommands.

    Args:
        owner (str): Command name used in error messages.
        initializer (Sequence[Argument]): Initializer arguments.
        subcommands (dict[str, Command]): Subcommands of the command.

    Raises:
        ConfigurationError: An initializer positional is optional.
    """
    if not subcommands:
        return

    for argument in positional_arguments(initializer):
        if argument.required or argument.pipe_required:
            continue

        raise ConfigurationError(
            f"Optional initializer positional parameter '{argument.display_name}' in "
            f"'{owner}' is not allowed because the command has subcommands"
        )


def validate_initializer_positionals(
    initializer: Sequence[Argument],
    *,
    owner: str,
    subcommands: dict[str, Command],
) -> None:
    """
    Validate initializer positionals of a command that may have subcommands.

    Args:
        initializer (Sequence[Argument]): Initializer arguments in declaration order.
        owner (str): Command name used in error messages.
        subcommands (dict[str, Command]): Subcommands of the command.

    Raises:
        ConfigurationError: Positional order is ambiguous or an initializer positional is
            optional while subcommands exist.
    """
    validate_positional_order(initializer, owner=owner)
    validate_optional_initializer_positionals(
        owner=owner,
        initializer=initializer,
        subcommands=subcommands,
    )


def validate_optional_positional_shape(name: str, value_shape: ValueShape) -> None:
    """
    Reject optional positionals whose value shape cannot be omitted unambiguously.

    Args:
        name (str): Parameter name used in error messages.
        value_shape (ValueShape): Value shape of the optional positional.

    Raises:
        ConfigurationError: The optional positional is a fixed tuple.
    """
    if value_shape is ValueShape.TUPLE:
        raise ConfigurationError(f"Optional tuple positional parameter '{name}' is not supported")


def validate_executable_flags_against_tokens(
    executable_flags: Sequence[ExecutableFlag],
    taken_tokens: set[str],
    *,
    help_flags: Sequence[str],
) -> None:
    """
    Reject executable flags that reuse help flags or already-claimed tokens.

    Args:
        executable_flags (Sequence[ExecutableFlag]): Executable flags to check.
        taken_tokens (set[str]): Option tokens already claimed in the same scope.
        help_flags (Sequence[str]): Help flag spellings.

    Raises:
        ReservedFlagError: An executable flag token is reserved or taken.
    """
    executable_tokens = executable_flag_tokens(executable_flags)
    for help_flag in help_flags:
        if help_flag in executable_tokens:
            raise ReservedFlagError(help_flag)

    for token in executable_tokens:
        if token in taken_tokens:
            raise ReservedFlagError(token)


def validate_schema_executable_flags(schema: ParserSchema, *, help_flags: Sequence[str]) -> None:
    """
    Validate parser-root executable flags against help flags and a single leaf command.

    Args:
        schema (ParserSchema): Finalized schema.
        help_flags (Sequence[str]): Help flag spellings.

    Raises:
        ReservedFlagError: Executable flags collide with help flags or command options.
    """
    parser_executable_flags = list(schema.executable_flags)
    validate_executable_flags_against_tokens(parser_executable_flags, set(), help_flags=help_flags)
    single_cmd = next(iter(schema.commands.values())) if len(schema.commands) == 1 else None
    if single_cmd is None or not single_cmd.is_leaf:
        return

    validate_executable_flags_against_tokens(
        parser_executable_flags,
        command_option_strings(single_cmd),
        help_flags=help_flags,
    )
    validate_executable_flags_against_tokens(
        single_cmd.executable_flags,
        executable_flag_tokens(parser_executable_flags),
        help_flags=help_flags,
    )


__all__ = [
    "argument_option_strings",
    "command_option_strings",
    "positional_arguments",
    "validate_command_mapping",
    "validate_executable_flags_against_tokens",
    "validate_initializer_positionals",
    "validate_optional_initializer_positionals",
    "validate_optional_positional_shape",
    "validate_parser_schema",
    "validate_positional_order",
    "validate_schema_executable_flags",
]

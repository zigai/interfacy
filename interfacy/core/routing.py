from __future__ import annotations

from collections.abc import Collection, Sequence

from interfacy.schema.nodes import Command, find_command


def select_commands(
    commands: dict[str, Command],
    args: Sequence[str],
    *,
    allow_args_from_file: bool,
    root_flags: Collection[str],
) -> frozenset[str]:
    """
    Return the canonical names of the top-level commands that ``args`` can reach.

    Root options take no values, so the first token that is not an option names the command.
    An argument file before that token can name any command.
    """
    if len(commands) == 1:
        return frozenset(commands)

    for arg in args:
        if arg in root_flags:
            return frozenset()
        if allow_args_from_file and arg.startswith("@"):
            return frozenset(commands)
        if arg.startswith("-"):
            continue

        command = find_command(commands, arg)

        return frozenset() if command is None else frozenset((command.canonical_name,))

    return frozenset()


__all__ = ["select_commands"]

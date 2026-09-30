from __future__ import annotations

import argparse
import re
from collections.abc import Mapping, Sequence

from interfacy.exceptions import UsageError

MISSING_ARGUMENTS_MARKER = "the following arguments are required:"


class ArgparseParseError(UsageError):
    """Internal recoverable argparse parse error."""


def is_missing_subcommand_error(
    message: str,
    actions: Sequence[argparse.Action],
    original_destinations: Mapping[str, str],
) -> bool:
    """
    Return whether an argparse error reports a missing subcommand.

    Args:
        message (str): Error message produced by argparse.
        actions (Sequence[argparse.Action]): Actions registered on the failing parser.
        original_destinations (Mapping[str, str]): Nested-to-original destination mapping.
    """
    if MISSING_ARGUMENTS_MARKER not in message:
        return False

    subparser_actions = [
        action for action in actions if isinstance(action, argparse._SubParsersAction)
    ]
    subparser_dests: set[str] = {action.dest for action in subparser_actions}
    if not subparser_dests:
        return False

    subparser_choices: set[str] = set()
    for action in subparser_actions:
        subparser_choices.update(action.choices.keys())

    missing_part = message.split(MISSING_ARGUMENTS_MARKER, 1)[1].strip()
    missing_names = [name.strip() for name in missing_part.split(",") if name.strip()]
    denested_missing = [original_destinations.get(name, name) for name in missing_names]
    denested_subparser_dests = {original_destinations.get(dest, dest) for dest in subparser_dests}
    brace_choices: set[str] = set()
    for grouped in re.findall(r"\{([^}]*)\}", missing_part):
        brace_choices.update(choice.strip() for choice in grouped.split(",") if choice)

    return any(name in denested_subparser_dests for name in denested_missing) or bool(
        brace_choices & subparser_choices
    )


__all__ = ["MISSING_ARGUMENTS_MARKER", "ArgparseParseError", "is_missing_subcommand_error"]

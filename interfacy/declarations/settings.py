from __future__ import annotations

from collections.abc import Sequence
from typing import Final, Literal, get_args

from interfacy.declarations.sorting import HelpOptionSortRule, HelpSubcommandSortRule

AbbreviationScope = Literal["top_level_options", "all_options"]
BackendName = Literal["argparse", "click"]
BACKEND_NAMES: Final[tuple[BackendName, ...]] = get_args(BackendName)
HelpOptionSort = list[HelpOptionSortRule] | None
HelpSubcommandSort = list[HelpSubcommandSortRule] | None
MethodSkips = Sequence[str] | None


BooleanNegativePrefix = str | None


HelpFlags = Sequence[str]


DEFAULT_HELP_FLAGS: tuple[str, ...] = ("--help",)


def reserved_names_for_help_flags(help_flags: Sequence[str]) -> list[str]:
    return [flag.lstrip("-") for flag in help_flags if flag.lstrip("-")]


__all__ = [
    "BACKEND_NAMES",
    "DEFAULT_HELP_FLAGS",
    "AbbreviationScope",
    "BackendName",
    "BooleanNegativePrefix",
    "HelpFlags",
    "HelpOptionSort",
    "HelpSubcommandSort",
    "MethodSkips",
    "reserved_names_for_help_flags",
]

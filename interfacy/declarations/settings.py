from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final, Literal, get_args

from interfacy.declarations.sorting import (
    HelpOptionSortRule,
    HelpSubcommandSortRule,
    resolve_help_option_sort_rules,
    resolve_help_subcommand_sort_rules,
)
from interfacy.exceptions import ConfigurationError

AbbreviationScope = Literal["top_level_options", "all_options"]
BackendName = Literal["argparse", "click"]
BACKEND_NAMES: Final[tuple[BackendName, ...]] = get_args(BackendName)
HelpOptionSort = list[HelpOptionSortRule] | None
HelpSubcommandSort = list[HelpSubcommandSortRule] | None
MethodSkips = Sequence[str] | None

ABBREVIATION_SCOPE_VALUES: tuple[AbbreviationScope, ...] = (
    "top_level_options",
    "all_options",
)


def validate_abbreviation_scope(value: AbbreviationScope) -> AbbreviationScope:
    if value not in ABBREVIATION_SCOPE_VALUES:
        raise ConfigurationError(
            "abbreviation_scope must be one of: " + ", ".join(ABBREVIATION_SCOPE_VALUES)
        )

    return value


def validate_help_option_sort(value: Any) -> HelpOptionSort:
    return resolve_help_option_sort_rules(value, value_name="help_option_sort")


def validate_help_subcommand_sort(value: Any) -> HelpSubcommandSort:
    return resolve_help_subcommand_sort_rules(value, value_name="help_subcommand_sort")


def validate_model_expansion_max_depth(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigurationError("model_expansion_max_depth must be an integer >= 1")
    if value < 1:
        raise ConfigurationError("model_expansion_max_depth must be >= 1")

    return value


def validate_method_skips(value: MethodSkips) -> list[str]:
    if value is None:
        return ["__init__", "__repr__", "repr"]

    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ConfigurationError("method_skips must be a sequence of strings")

    for item in value:
        if not isinstance(item, str):
            raise ConfigurationError("method_skips values must be strings")

    return list(dict.fromkeys(value))


def validate_help_group(
    value: Any,
    *,
    value_name: str = "help_group",
    allow_none: bool = True,
) -> str | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{value_name} must be a non-empty string")

    return value


BooleanNegativePrefix = str | None


HelpFlags = Sequence[str]


DEFAULT_HELP_FLAGS: tuple[str, ...] = ("--help",)


def validate_abbreviation_max_generated_len(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigurationError("abbreviation_max_generated_len must be an integer >= 1")
    if value < 1:
        raise ConfigurationError("abbreviation_max_generated_len must be >= 1")

    return value


def validate_parse_recovery_max_attempts(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigurationError("parse_recovery_max_attempts must be an integer >= 0")
    if value < 0:
        raise ConfigurationError("parse_recovery_max_attempts must be >= 0")

    return value


def validate_bool_negative_prefix(value: BooleanNegativePrefix) -> BooleanNegativePrefix:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigurationError("bool_negative_prefix must be a string or None")
    if not value:
        raise ConfigurationError("bool_negative_prefix must not be empty")

    return value


def validate_help_flags(value: HelpFlags) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ConfigurationError("help_flags must be a sequence of flag strings")

    for item in value:
        if not isinstance(item, str) or not item.startswith("-") or item == "-":
            raise ConfigurationError("help_flags values must start with '-' or '--'")
    result = tuple(dict.fromkeys(value))
    if not result:
        raise ConfigurationError("help_flags must contain at least one flag")

    return result


def reserved_names_for_help_flags(help_flags: Sequence[str]) -> list[str]:
    return [flag.lstrip("-") for flag in help_flags if flag.lstrip("-")]


__all__ = [
    "BACKEND_NAMES",
    "DEFAULT_HELP_FLAGS",
    "BooleanNegativePrefix",
    "HelpFlags",
    "reserved_names_for_help_flags",
    "validate_abbreviation_max_generated_len",
    "validate_bool_negative_prefix",
    "validate_help_flags",
    "validate_help_group",
    "validate_parse_recovery_max_attempts",
]

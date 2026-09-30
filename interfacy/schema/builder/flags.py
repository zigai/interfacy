from __future__ import annotations

from typing import Any

from objinspect import Parameter

from interfacy.declarations.params import Param
from interfacy.exceptions import ConfigurationError, ReservedFlagError
from interfacy.naming.flag_strategy import (
    FlagAllocationState,
    get_arg_flags_for_parameter,
    inverted_bool_flag_name,
)


def flag_token_key(flag: str) -> str:
    """
    Return the reservation key of a flag spelling (the flag without leading dashes).

    Args:
        flag (str): Flag spelling.
    """
    return flag.lstrip("-")


def reserve_parameter_flags(flags: tuple[str, ...], taken_flags: list[str]) -> None:
    """
    Reserve one parameter's flag spellings, rejecting duplicates and taken names.

    Args:
        flags (tuple[str, ...]): Flag spellings of one parameter.
        taken_flags (list[str]): Reserved flag keys, updated in place.

    Raises:
        ReservedFlagError: A spelling repeats or is already reserved.
    """
    seen_in_param: set[str] = set()
    for flag in flags:
        if flag in seen_in_param:
            raise ReservedFlagError(flag_token_key(flag))

        seen_in_param.add(flag)

        key = flag_token_key(flag)
        if key in taken_flags:
            raise ReservedFlagError(key)

    for flag in flags:
        key = flag_token_key(flag)
        if key not in taken_flags:
            taken_flags.append(key)


def release_short_flags(flags: tuple[str, ...], taken_flags: list[str]) -> None:
    """
    Release the reservations of single-dash flags.

    Args:
        flags (tuple[str, ...]): Flag spellings whose short forms are released.
        taken_flags (list[str]): Reserved flag keys, updated in place.
    """
    for flag in flags:
        if flag.startswith("-") and not flag.startswith("--"):
            short_name = flag_token_key(flag)
            if short_name in taken_flags:
                taken_flags.remove(short_name)


def short_flag_from_setting(
    setting: Param,
    *,
    abbrev_name: str,
    taken_flags: list[str],
    abbreviation_gen: Any,
) -> str | None:
    """
    Return the short flag requested by a parameter setting, generating one if asked.

    Args:
        setting (Param): Parameter setting.
        abbrev_name (str): Name used to generate an abbreviation.
        taken_flags (list[str]): Reserved flag keys.
        abbreviation_gen (Any): Abbreviation generator.
    """
    if setting.short is False:
        return None
    if isinstance(setting.short, str):
        return setting.short
    if setting.short is True or setting.short is None:
        short = abbreviation_gen.generate(abbrev_name, list(taken_flags))
        return f"-{short.strip()}" if short else None

    return None


def flags_from_parameter_setting(
    *,
    translated_name: str,
    param: Parameter,
    setting: Param,
    taken_flags: list[str],
    abbreviation_gen: Any,
) -> tuple[str, ...]:
    """
    Return and reserve option flags configured through a parameter setting.

    Args:
        translated_name (str): CLI-translated parameter name.
        param (Parameter): Inspected parameter.
        setting (Param): Parameter setting.
        taken_flags (list[str]): Reserved flag keys, updated in place.
        abbreviation_gen (Any): Abbreviation generator.
    """
    if setting.flags is not None:
        flags = tuple(setting.flags)
        reserve_parameter_flags(flags, taken_flags)
        return flags

    long_flag = setting.long or f"--{translated_name}"
    flags: tuple[str, ...] = (long_flag,)
    abbrev_name = long_flag.lstrip("-")
    if param.is_typed and param.type is bool:
        default_value = param.default if param.has_default else False
        if default_value is True:
            abbrev_name = f"no-{abbrev_name}"

    short_flag = short_flag_from_setting(
        setting,
        abbrev_name=abbrev_name,
        taken_flags=taken_flags,
        abbreviation_gen=abbreviation_gen,
    )
    if short_flag and short_flag not in flags:
        flags = (short_flag, long_flag)

    reserve_parameter_flags(flags, taken_flags)

    return flags


def flags_for_parameter(
    *,
    translated_name: str,
    param: Parameter,
    taken_flags: list[str],
    flag_allocation_state: FlagAllocationState | None,
    parameter_setting: Param | None,
    flag_strategy: Any,
    abbreviation_gen: Any,
) -> tuple[str, ...]:
    """
    Allocate and reserve the flags of one parameter.

    Explicit parameter settings take precedence over the flag strategy.

    Args:
        translated_name (str): CLI-translated parameter name.
        param (Parameter): Inspected parameter.
        taken_flags (list[str]): Reserved flag keys, updated in place.
        flag_allocation_state (FlagAllocationState | None): Strategy allocation state.
        parameter_setting (Param | None): Explicit parameter setting.
        flag_strategy (Any): Flag strategy.
        abbreviation_gen (Any): Abbreviation generator.

    Raises:
        ReservedFlagError: The parameter name or one of its flags is already reserved.
    """
    if parameter_setting is not None and parameter_setting.kind == "positional":
        if translated_name in taken_flags:
            raise ReservedFlagError(translated_name)

        taken_flags.append(translated_name)

        return (translated_name,)

    if parameter_setting is not None and (
        parameter_setting.kind == "option" or parameter_setting.has_flag_overrides
    ):
        return flags_from_parameter_setting(
            translated_name=translated_name,
            param=param,
            setting=parameter_setting,
            taken_flags=taken_flags,
            abbreviation_gen=abbreviation_gen,
        )

    if translated_name in taken_flags:
        raise ReservedFlagError(translated_name)

    flags = get_arg_flags_for_parameter(
        flag_strategy,
        translated_name,
        param,
        taken_flags,
        abbreviation_gen,
        allocation_state=flag_allocation_state,
    )
    taken_flags.append(translated_name)

    return flags


def generated_negative_flags(
    name: str,
    flags: tuple[str, ...],
    *,
    bool_negative_prefix: str | None,
) -> tuple[str, ...]:
    """
    Return the negative flag generated from a boolean parameter's primary long flag.

    Args:
        name (str): Parameter name used in error messages.
        flags (tuple[str, ...]): Positive flag spellings.
        bool_negative_prefix (str | None): Negative prefix, or None to disable generation.

    Raises:
        ConfigurationError: The positive flags include no long option.
    """
    if bool_negative_prefix is None:
        return ()

    long_flags = [flag for flag in flags if flag.startswith("--")]
    if not long_flags:
        raise ConfigurationError(
            f"Boolean parameter '{name}' requires Param.negative_flags because its "
            "positive flags do not include a long option"
        )

    primary_long_name = long_flags[0][2:]
    negative_name = inverted_bool_flag_name(primary_long_name, prefix=bool_negative_prefix)
    return (f"--{negative_name}",)


__all__ = [
    "flag_token_key",
    "flags_for_parameter",
    "flags_from_parameter_setting",
    "generated_negative_flags",
    "release_short_flags",
    "reserve_parameter_flags",
    "short_flag_from_setting",
]

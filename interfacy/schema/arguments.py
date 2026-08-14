from collections.abc import Callable
from dataclasses import dataclass
from inspect import _ParameterKind
from typing import Any

from interfacy.schema.schema import ArgumentDefault, BooleanBehavior, ValueShape
from interfacy.schema.sorting import HelpOptionSortRule, HelpSubcommandSortRule
from interfacy.schema.value_plan import ArgumentValue, ValueCardinality


@dataclass
class ParamSpec:
    name: str
    type: Any
    is_typed: bool
    has_default: bool
    default: Any
    is_required: bool
    is_optional: bool
    kind: _ParameterKind
    description: str | None = None


@dataclass
class ArgumentBuildState:
    parser_func: Callable[[str], Any] | None
    value_shape: ValueShape
    cardinality: ValueCardinality
    argument_default: ArgumentDefault
    parsed_type: Any | None
    choices: tuple[Any, ...] | None
    boolean_behavior: BooleanBehavior | None
    is_optional_union_list: bool = False
    tuple_element_parsers: tuple[Callable[[str], Any], ...] | None = None
    value_plan: ArgumentValue | None = None


@dataclass(frozen=True)
class EffectiveCommandSettings:
    include_inherited_methods: bool
    include_protected_methods: bool
    include_private_methods: bool
    include_staticmethods: bool
    include_classmethods: bool
    method_skips: list[str]
    expand_model_params: bool
    model_expansion_max_depth: int
    abbreviation_scope: str
    help_option_sort: list[HelpOptionSortRule]
    help_subcommand_sort: list[HelpSubcommandSortRule]


@dataclass(frozen=True)
class CommandOverrides:
    include_inherited_methods: bool | None = None
    include_protected_methods: bool | None = None
    include_private_methods: bool | None = None
    include_staticmethods: bool | None = None
    include_classmethods: bool | None = None
    method_skips: list[str] | None = None
    expand_model_params: bool | None = None
    model_expansion_max_depth: int | None = None
    abbreviation_scope: str | None = None
    help_option_sort: list[HelpOptionSortRule] | None = None
    help_subcommand_sort: list[HelpSubcommandSortRule] | None = None


def resolve_command_settings(
    base: EffectiveCommandSettings,
    overrides: CommandOverrides,
) -> EffectiveCommandSettings:
    return EffectiveCommandSettings(
        include_inherited_methods=(
            overrides.include_inherited_methods
            if overrides.include_inherited_methods is not None
            else base.include_inherited_methods
        ),
        include_protected_methods=(
            overrides.include_protected_methods
            if overrides.include_protected_methods is not None
            else base.include_protected_methods
        ),
        include_private_methods=(
            overrides.include_private_methods
            if overrides.include_private_methods is not None
            else base.include_private_methods
        ),
        include_staticmethods=(
            overrides.include_staticmethods
            if overrides.include_staticmethods is not None
            else base.include_staticmethods
        ),
        include_classmethods=(
            overrides.include_classmethods
            if overrides.include_classmethods is not None
            else base.include_classmethods
        ),
        method_skips=(
            list(overrides.method_skips)
            if overrides.method_skips is not None
            else list(base.method_skips)
        ),
        expand_model_params=(
            overrides.expand_model_params
            if overrides.expand_model_params is not None
            else base.expand_model_params
        ),
        model_expansion_max_depth=(
            overrides.model_expansion_max_depth
            if overrides.model_expansion_max_depth is not None
            else base.model_expansion_max_depth
        ),
        abbreviation_scope=(
            overrides.abbreviation_scope
            if overrides.abbreviation_scope is not None
            else base.abbreviation_scope
        ),
        help_option_sort=(
            list(overrides.help_option_sort)
            if overrides.help_option_sort is not None
            else list(base.help_option_sort)
        ),
        help_subcommand_sort=(
            list(overrides.help_subcommand_sort)
            if overrides.help_subcommand_sort is not None
            else list(base.help_subcommand_sort)
        ),
    )


__all__ = [
    "ArgumentBuildState",
    "CommandOverrides",
    "EffectiveCommandSettings",
    "ParamSpec",
    "resolve_command_settings",
]

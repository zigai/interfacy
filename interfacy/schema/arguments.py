from collections.abc import Callable, Sequence
from dataclasses import dataclass, fields, replace
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
    method_skips: Sequence[str] | None = None
    expand_model_params: bool | None = None
    model_expansion_max_depth: int | None = None
    abbreviation_scope: str | None = None
    help_option_sort: list[HelpOptionSortRule] | None = None
    help_subcommand_sort: list[HelpSubcommandSortRule] | None = None


def resolve_command_settings(
    base: EffectiveCommandSettings,
    overrides: CommandOverrides,
) -> EffectiveCommandSettings:
    updates: dict[str, Any] = {}
    for f in fields(overrides):
        val = getattr(overrides, f.name)
        if val is not None:
            if f.name == "method_skips":
                updates[f.name] = list(val)
            else:
                updates[f.name] = list(val) if isinstance(val, list) else val
    return replace(base, **updates)


__all__ = [
    "ArgumentBuildState",
    "CommandOverrides",
    "EffectiveCommandSettings",
    "ParamSpec",
    "resolve_command_settings",
]

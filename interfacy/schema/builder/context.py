from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from inspect import _ParameterKind
from typing import Any

from interfacy.declarations.executable_flags import ExecutableFlag
from interfacy.declarations.pipes import PipeTargets
from interfacy.declarations.sorting import HelpOptionSortRule, HelpSubcommandSortRule
from interfacy.schema.model import ArgumentDefault, BooleanBehavior, Command, ValueShape
from interfacy.schema.values import ArgumentValue, ValueCardinality


@dataclass
class SchemaBuildContext:
    """Backend-neutral source and policy snapshot for schema construction."""

    pipe_target_resolver: Callable[..., PipeTargets | None]
    description: str | None
    epilog: str | None
    commands: dict[str, Command]
    command_key: str | None
    reserved_flags: list[str]
    method_skips: list[str]
    allow_args_from_file: bool
    pipe_targets_default: PipeTargets | None
    metadata: dict[str, Any]
    executable_flags: list[ExecutableFlag]
    type_parser: Any
    flag_strategy: Any
    abbreviation_gen: Any
    include_inherited_methods: bool
    include_protected_methods: bool
    include_private_methods: bool
    include_staticmethods: bool
    include_classmethods: bool
    expand_model_params: bool
    model_expansion_max_depth: int
    abbreviation_scope: str
    help_option_sort: Any
    help_subcommand_sort: Any
    help_option_sort_effective: list[HelpOptionSortRule]
    help_subcommand_sort_effective: list[HelpSubcommandSortRule]
    bool_negative_prefix: str | None
    help_flags: tuple[str, ...]


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


__all__ = [
    "ArgumentBuildState",
    "EffectiveCommandSettings",
    "ParamSpec",
    "SchemaBuildContext",
]

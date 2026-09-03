from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any, ClassVar, Final, Literal, TypeVar

from strto import StrToTypeParser
from typing_extensions import Self

from interfacy.exceptions import ConfigurationError
from interfacy.executable_flag import ExecutableFlag, normalize_executable_flags
from interfacy.help.content import HelpRenderer
from interfacy.help.layout import HelpLayout, InterfacyColors
from interfacy.naming import AbbreviationGenerator, FlagStrategy
from interfacy.pipe import PipeTargets, build_pipe_targets_config
from interfacy.plugins import InterfacyPlugin
from interfacy.schema.sorting import (
    HelpOptionSortRule,
    HelpSubcommandSortRule,
    resolve_help_option_sort_rules,
    resolve_help_subcommand_sort_rules,
)

AbbreviationScope = Literal["top_level_options", "all_options"]
BackendName = Literal["argparse", "click"]
BooleanNegativePrefix = str
HelpFlags = Sequence[str]
HelpOptionSort = list[HelpOptionSortRule] | None
HelpSubcommandSort = list[HelpSubcommandSortRule] | None
MethodSkips = Sequence[str] | None

ABBREVIATION_SCOPE_VALUES: tuple[AbbreviationScope, ...] = (
    "top_level_options",
    "all_options",
)
DEFAULT_HELP_FLAGS: tuple[str, ...] = ("--help",)
MAX_PARSE_RECOVERY_ATTEMPTS = 3
_T = TypeVar("_T")


class _UnsetType:
    __slots__ = ()

    _instance: ClassVar[_UnsetType | None] = None

    def __new__(cls) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final = _UnsetType()


_RESETTABLE_UPDATE_FIELDS: Final = frozenset(
    {
        "abbreviation_gen",
        "executable_flags",
        "flag_strategy",
        "help_colors",
        "help_renderer",
        "help_flags",
        "help_layout",
        "help_option_sort",
        "help_position",
        "help_subcommand_sort",
        "method_skips",
        "type_parser",
    }
)


@dataclass(kw_only=True)
class EngineSettings:
    description: str | None = None
    epilog: str | None = None
    type_parser: StrToTypeParser | None = None
    help_layout: HelpLayout | None = None
    help_colors: InterfacyColors | None = None
    help_renderer: HelpRenderer | None = None
    print_result: bool = False
    tab_completion: bool = False
    full_error_traceback: bool = False
    allow_args_from_file: bool = True
    flag_strategy: FlagStrategy | None = None
    abbreviation_gen: AbbreviationGenerator | None = None
    abbreviation_max_generated_len: int = 1
    abbreviation_scope: AbbreviationScope = "top_level_options"
    help_option_sort: HelpOptionSort = None
    help_subcommand_sort: HelpSubcommandSort = None
    help_position: int | None = None
    executable_flags: Sequence[ExecutableFlag] | None = None
    pipe_targets: PipeTargets | dict[str, Any] | Sequence[Any] | str | None = None
    print_result_func: Callable[[Any], Any] = print
    include_inherited_methods: bool = False
    include_protected_methods: bool = False
    include_private_methods: bool = False
    include_staticmethods: bool = True
    include_classmethods: bool = False
    on_interrupt: Callable[[KeyboardInterrupt], None] | None = None
    silent_interrupt: bool = True
    expand_model_params: bool = True
    model_expansion_max_depth: int = 3
    bool_negative_prefix: BooleanNegativePrefix = "no-"
    help_flags: HelpFlags = DEFAULT_HELP_FLAGS
    plugins: Sequence[InterfacyPlugin] | None = None
    method_skips: MethodSkips = None
    parse_recovery_max_attempts: int = MAX_PARSE_RECOVERY_ATTEMPTS

    def __post_init__(self) -> None:
        self.abbreviation_max_generated_len = validate_abbreviation_max_generated_len(
            self.abbreviation_max_generated_len
        )
        self.abbreviation_scope = validate_abbreviation_scope(self.abbreviation_scope)
        help_option_sort = validate_help_option_sort(
            list(self.help_option_sort)
            if isinstance(self.help_option_sort, tuple)
            else self.help_option_sort
        )
        self.help_option_sort = help_option_sort
        help_subcommand_sort = validate_help_subcommand_sort(
            list(self.help_subcommand_sort)
            if isinstance(self.help_subcommand_sort, tuple)
            else self.help_subcommand_sort
        )
        self.help_subcommand_sort = help_subcommand_sort
        self.parse_recovery_max_attempts = validate_parse_recovery_max_attempts(
            self.parse_recovery_max_attempts
        )
        self.method_skips = tuple(validate_method_skips(self.method_skips))
        self.bool_negative_prefix = validate_bool_negative_prefix(self.bool_negative_prefix)
        self.help_flags = validate_help_flags(self.help_flags)
        self.executable_flags = tuple(normalize_executable_flags(self.executable_flags))
        self.pipe_targets = (
            build_pipe_targets_config(self.pipe_targets) if self.pipe_targets is not None else None
        )
        self.plugins = tuple(self.plugins) if self.plugins is not None else None

    def parser_kwargs(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "epilog": self.epilog,
            "type_parser": self.type_parser,
            "help_layout": self.help_layout,
            "help_colors": self.help_colors,
            "print_result": self.print_result,
            "tab_completion": self.tab_completion,
            "full_error_traceback": self.full_error_traceback,
            "allow_args_from_file": self.allow_args_from_file,
            "flag_strategy": self.flag_strategy,
            "abbreviation_gen": self.abbreviation_gen,
            "abbreviation_max_generated_len": self.abbreviation_max_generated_len,
            "abbreviation_scope": self.abbreviation_scope,
            "help_option_sort": (
                list(self.help_option_sort) if self.help_option_sort is not None else None
            ),
            "help_subcommand_sort": (
                list(self.help_subcommand_sort) if self.help_subcommand_sort is not None else None
            ),
            "help_position": self.help_position,
            "executable_flags": self.executable_flags,
            "pipe_targets": self.pipe_targets,
            "print_result_func": self.print_result_func,
            "include_inherited_methods": self.include_inherited_methods,
            "include_protected_methods": self.include_protected_methods,
            "include_private_methods": self.include_private_methods,
            "include_staticmethods": self.include_staticmethods,
            "include_classmethods": self.include_classmethods,
            "on_interrupt": self.on_interrupt,
            "silent_interrupt": self.silent_interrupt,
            "expand_model_params": self.expand_model_params,
            "model_expansion_max_depth": self.model_expansion_max_depth,
            "bool_negative_prefix": self.bool_negative_prefix,
            "help_flags": self.help_flags,
            "plugins": self.plugins,
            "method_skips": self.method_skips,
            "parse_recovery_max_attempts": self.parse_recovery_max_attempts,
        }


@dataclass(frozen=True, kw_only=True)
class _EngineSettingsUpdate:
    help_layout: _UnsetType | HelpLayout | None = UNSET
    help_colors: _UnsetType | InterfacyColors | None = UNSET
    help_renderer: _UnsetType | HelpRenderer | None = UNSET
    type_parser: _UnsetType | StrToTypeParser | None = UNSET
    print_result: _UnsetType | bool | None = UNSET
    tab_completion: _UnsetType | bool | None = UNSET
    full_error_traceback: _UnsetType | bool | None = UNSET
    allow_args_from_file: _UnsetType | bool | None = UNSET
    flag_strategy: _UnsetType | FlagStrategy | None = UNSET
    abbreviation_gen: _UnsetType | AbbreviationGenerator | None = UNSET
    abbreviation_max_generated_len: _UnsetType | int | None = UNSET
    abbreviation_scope: _UnsetType | AbbreviationScope | None = UNSET
    help_option_sort: _UnsetType | HelpOptionSort = UNSET
    help_subcommand_sort: _UnsetType | HelpSubcommandSort = UNSET
    help_position: _UnsetType | int | None = UNSET
    executable_flags: _UnsetType | Sequence[ExecutableFlag] | None = UNSET
    include_inherited_methods: _UnsetType | bool | None = UNSET
    include_protected_methods: _UnsetType | bool | None = UNSET
    include_private_methods: _UnsetType | bool | None = UNSET
    include_staticmethods: _UnsetType | bool | None = UNSET
    include_classmethods: _UnsetType | bool | None = UNSET
    silent_interrupt: _UnsetType | bool | None = UNSET
    expand_model_params: _UnsetType | bool | None = UNSET
    model_expansion_max_depth: _UnsetType | int | None = UNSET
    bool_negative_prefix: _UnsetType | BooleanNegativePrefix | None = UNSET
    help_flags: _UnsetType | HelpFlags | None = UNSET
    plugins: _UnsetType | Sequence[InterfacyPlugin] | None = UNSET
    method_skips: _UnsetType | MethodSkips = UNSET
    parse_recovery_max_attempts: _UnsetType | int | None = UNSET


@dataclass(frozen=True, kw_only=True)
class _PreparedEngineSettings:
    settings: EngineSettings
    plugin_additions: tuple[InterfacyPlugin, ...]
    changed_fields: frozenset[str]
    reset_fields: frozenset[str]


def _resolve_required_update(
    field_name: str,
    value: _UnsetType | _T | None,
    current: _T,
) -> _T:
    if isinstance(value, _UnsetType):
        return current
    if value is None:
        raise ConfigurationError(f"{field_name} cannot be None")
    return value


def _resolve_resettable_update(
    value: _UnsetType | _T | None,
    current: _T | None,
) -> _T | None:
    if isinstance(value, _UnsetType):
        return current
    return value


def _prepare_settings_update(
    current: EngineSettings,
    update: _EngineSettingsUpdate,
) -> _PreparedEngineSettings:
    update_values = vars(update)
    changed_fields = frozenset(
        field_name for field_name, value in update_values.items() if value is not UNSET
    )
    reset_fields = frozenset(
        field_name
        for field_name in changed_fields
        if field_name in _RESETTABLE_UPDATE_FIELDS and update_values[field_name] is None
    )

    if isinstance(update.plugins, _UnsetType):
        plugin_additions: tuple[InterfacyPlugin, ...] = ()
    elif update.plugins is None:
        raise ConfigurationError("plugins cannot be None")
    else:
        plugin_additions = tuple(update.plugins)
        if any(not isinstance(plugin, InterfacyPlugin) for plugin in plugin_additions):
            raise ConfigurationError("plugins must contain InterfacyPlugin instances")

    settings = replace(
        current,
        help_layout=_resolve_resettable_update(update.help_layout, current.help_layout),
        help_colors=_resolve_resettable_update(update.help_colors, current.help_colors),
        help_renderer=_resolve_resettable_update(
            update.help_renderer,
            current.help_renderer,
        ),
        type_parser=_resolve_resettable_update(update.type_parser, current.type_parser),
        print_result=_resolve_required_update(
            "print_result", update.print_result, current.print_result
        ),
        tab_completion=_resolve_required_update(
            "tab_completion", update.tab_completion, current.tab_completion
        ),
        full_error_traceback=_resolve_required_update(
            "full_error_traceback",
            update.full_error_traceback,
            current.full_error_traceback,
        ),
        allow_args_from_file=_resolve_required_update(
            "allow_args_from_file",
            update.allow_args_from_file,
            current.allow_args_from_file,
        ),
        flag_strategy=_resolve_resettable_update(update.flag_strategy, current.flag_strategy),
        abbreviation_gen=_resolve_resettable_update(
            update.abbreviation_gen, current.abbreviation_gen
        ),
        abbreviation_max_generated_len=_resolve_required_update(
            "abbreviation_max_generated_len",
            update.abbreviation_max_generated_len,
            current.abbreviation_max_generated_len,
        ),
        abbreviation_scope=_resolve_required_update(
            "abbreviation_scope",
            update.abbreviation_scope,
            current.abbreviation_scope,
        ),
        help_option_sort=_resolve_resettable_update(
            update.help_option_sort, current.help_option_sort
        ),
        help_subcommand_sort=_resolve_resettable_update(
            update.help_subcommand_sort, current.help_subcommand_sort
        ),
        help_position=_resolve_resettable_update(update.help_position, current.help_position),
        executable_flags=_resolve_resettable_update(
            update.executable_flags, current.executable_flags
        ),
        include_inherited_methods=_resolve_required_update(
            "include_inherited_methods",
            update.include_inherited_methods,
            current.include_inherited_methods,
        ),
        include_protected_methods=_resolve_required_update(
            "include_protected_methods",
            update.include_protected_methods,
            current.include_protected_methods,
        ),
        include_private_methods=_resolve_required_update(
            "include_private_methods",
            update.include_private_methods,
            current.include_private_methods,
        ),
        include_staticmethods=_resolve_required_update(
            "include_staticmethods",
            update.include_staticmethods,
            current.include_staticmethods,
        ),
        include_classmethods=_resolve_required_update(
            "include_classmethods",
            update.include_classmethods,
            current.include_classmethods,
        ),
        silent_interrupt=_resolve_required_update(
            "silent_interrupt", update.silent_interrupt, current.silent_interrupt
        ),
        expand_model_params=_resolve_required_update(
            "expand_model_params",
            update.expand_model_params,
            current.expand_model_params,
        ),
        model_expansion_max_depth=_resolve_required_update(
            "model_expansion_max_depth",
            update.model_expansion_max_depth,
            current.model_expansion_max_depth,
        ),
        bool_negative_prefix=_resolve_required_update(
            "bool_negative_prefix",
            update.bool_negative_prefix,
            current.bool_negative_prefix,
        ),
        help_flags=(
            DEFAULT_HELP_FLAGS
            if update.help_flags is None
            else _resolve_required_update("help_flags", update.help_flags, current.help_flags)
        ),
        method_skips=_resolve_resettable_update(update.method_skips, current.method_skips),
        parse_recovery_max_attempts=_resolve_required_update(
            "parse_recovery_max_attempts",
            update.parse_recovery_max_attempts,
            current.parse_recovery_max_attempts,
        ),
    )
    return _PreparedEngineSettings(
        settings=settings,
        plugin_additions=plugin_additions,
        changed_fields=changed_fields,
        reset_fields=reset_fields,
    )


def validate_abbreviation_max_generated_len(value: int) -> int:
    if value < 1:
        raise ConfigurationError("abbreviation_max_generated_len must be >= 1")

    return value


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
    if value < 1:
        raise ConfigurationError("model_expansion_max_depth must be >= 1")

    return value


def validate_parse_recovery_max_attempts(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigurationError("parse_recovery_max_attempts must be an integer >= 0")
    if value < 0:
        raise ConfigurationError("parse_recovery_max_attempts must be >= 0")

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


def validate_bool_negative_prefix(value: BooleanNegativePrefix) -> BooleanNegativePrefix:
    if not isinstance(value, str) or not value:
        raise ConfigurationError("bool_negative_prefix must be a non-empty string")
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
    "DEFAULT_HELP_FLAGS",
    "MAX_PARSE_RECOVERY_ATTEMPTS",
    "UNSET",
    "AbbreviationScope",
    "BackendName",
    "BooleanNegativePrefix",
    "EngineSettings",
    "HelpFlags",
    "HelpOptionSort",
    "HelpSubcommandSort",
    "MethodSkips",
]

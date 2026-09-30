from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, fields, replace
from types import MappingProxyType
from typing import Any, Final

from strto import StrToTypeParser

from interfacy.common.sentinels import UNSET
from interfacy.declarations.executable_flags import ExecutableFlag, normalize_executable_flags
from interfacy.declarations.pipes import PipeTargets, build_pipe_targets_config
from interfacy.declarations.settings import (
    DEFAULT_HELP_FLAGS,
    AbbreviationScope,
    BooleanNegativePrefix,
    HelpFlags,
    HelpOptionSort,
    HelpSubcommandSort,
    MethodSkips,
    validate_abbreviation_max_generated_len,
    validate_abbreviation_scope,
    validate_bool_negative_prefix,
    validate_help_flags,
    validate_help_option_sort,
    validate_help_subcommand_sort,
    validate_method_skips,
    validate_model_expansion_max_depth,
    validate_parse_recovery_max_attempts,
)
from interfacy.exceptions import ConfigurationError
from interfacy.help.colors import InterfacyColors
from interfacy.help.content import HelpRenderer
from interfacy.help.layouts import HelpLayout
from interfacy.naming import AbbreviationGenerator, FlagStrategy
from interfacy.plugins import InterfacyPlugin

MAX_PARSE_RECOVERY_ATTEMPTS = 3


# ``update`` metadata says how ``apply_setup`` treats a setting. Settings without it are
# construction-only. ``required`` rejects ``None``; ``resettable`` treats ``None`` as a reset to
# the field default; ``additive`` appends to the current value and rejects ``None``.
REQUIRED: Final = MappingProxyType({"update": "required"})
RESETTABLE: Final = MappingProxyType({"update": "resettable"})
ADDITIVE: Final = MappingProxyType({"update": "additive"})


@dataclass(kw_only=True)
class EngineSettings:
    description: str | None = None
    epilog: str | None = None
    type_parser: StrToTypeParser | None = field(default=None, metadata=RESETTABLE)
    help_layout: HelpLayout | None = field(default=None, metadata=RESETTABLE)
    help_colors: InterfacyColors | None = field(default=None, metadata=RESETTABLE)
    help_renderer: HelpRenderer | None = field(default=None, metadata=RESETTABLE)
    print_result: bool = field(default=False, metadata=REQUIRED)
    tab_completion: bool = field(default=False, metadata=REQUIRED)
    full_error_traceback: bool = field(default=False, metadata=REQUIRED)
    allow_args_from_file: bool = field(default=True, metadata=REQUIRED)
    flag_strategy: FlagStrategy | None = field(default=None, metadata=RESETTABLE)
    abbreviation_gen: AbbreviationGenerator | None = field(default=None, metadata=RESETTABLE)
    abbreviation_max_generated_len: int = field(default=1, metadata=REQUIRED)
    abbreviation_scope: AbbreviationScope = field(default="top_level_options", metadata=REQUIRED)
    help_option_sort: HelpOptionSort = field(default=None, metadata=RESETTABLE)
    help_subcommand_sort: HelpSubcommandSort = field(default=None, metadata=RESETTABLE)
    help_position: int | None = field(default=None, metadata=RESETTABLE)
    executable_flags: Sequence[ExecutableFlag] | None = field(default=None, metadata=RESETTABLE)
    pipe_targets: PipeTargets | dict[str, Any] | Sequence[Any] | str | None = None
    print_result_func: Callable[[Any], Any] = print
    include_inherited_methods: bool = field(default=False, metadata=REQUIRED)
    include_protected_methods: bool = field(default=False, metadata=REQUIRED)
    include_private_methods: bool = field(default=False, metadata=REQUIRED)
    include_staticmethods: bool = field(default=True, metadata=REQUIRED)
    include_classmethods: bool = field(default=False, metadata=REQUIRED)
    on_interrupt: Callable[[KeyboardInterrupt], None] | None = None
    silent_interrupt: bool = field(default=True, metadata=REQUIRED)
    expand_model_params: bool = field(default=True, metadata=REQUIRED)
    model_expansion_max_depth: int = field(default=3, metadata=REQUIRED)
    bool_negative_prefix: BooleanNegativePrefix = field(default="no-", metadata=REQUIRED)
    help_flags: HelpFlags = field(default=DEFAULT_HELP_FLAGS, metadata=RESETTABLE)
    plugins: Sequence[InterfacyPlugin] | None = field(default=None, metadata=ADDITIVE)
    method_skips: MethodSkips = field(default=None, metadata=RESETTABLE)
    parse_recovery_max_attempts: int = field(default=MAX_PARSE_RECOVERY_ATTEMPTS, metadata=REQUIRED)

    def __post_init__(self) -> None:
        self.abbreviation_max_generated_len = validate_abbreviation_max_generated_len(
            self.abbreviation_max_generated_len
        )
        self.abbreviation_scope = validate_abbreviation_scope(self.abbreviation_scope)
        self.model_expansion_max_depth = validate_model_expansion_max_depth(
            self.model_expansion_max_depth
        )
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


SETTING_NAMES: Final = frozenset(setting.name for setting in fields(EngineSettings))
UPDATE_POLICIES: Final[Mapping[str, str]] = MappingProxyType(
    {
        setting.name: setting.metadata["update"]
        for setting in fields(EngineSettings)
        if "update" in setting.metadata
    }
)


@dataclass(frozen=True, kw_only=True)
class PreparedEngineSettings:
    settings: EngineSettings
    plugin_additions: tuple[InterfacyPlugin, ...]
    changed_fields: frozenset[str]
    reset_fields: frozenset[str]


def _field_default(name: str) -> Any:
    return next(setting.default for setting in fields(EngineSettings) if setting.name == name)


def prepare_settings_update(
    current: EngineSettings,
    changes: Mapping[str, Any],
) -> PreparedEngineSettings:
    """
    Validate ``apply_setup`` changes against ``current`` without mutating it.

    ``UNSET`` values keep the current setting. See ``UPDATE_POLICIES`` for how ``None`` and
    additive settings are handled.

    Raises:
        TypeError: If a change names a setting that cannot be updated.
        ConfigurationError: If a change is invalid.
    """
    unknown = sorted(set(changes) - UPDATE_POLICIES.keys())
    if unknown:
        raise TypeError(f"apply_setup() got unexpected keyword arguments: {', '.join(unknown)}")

    replacements: dict[str, Any] = {}
    reset_fields: set[str] = set()
    plugin_additions: tuple[InterfacyPlugin, ...] = ()
    for name, value in changes.items():
        if value is UNSET:
            continue

        policy = UPDATE_POLICIES[name]
        if value is None and policy != "resettable":
            raise ConfigurationError(f"{name} cannot be None")

        if policy == "additive":
            plugin_additions = tuple(value)
            if any(not isinstance(plugin, InterfacyPlugin) for plugin in plugin_additions):
                raise ConfigurationError("plugins must contain InterfacyPlugin instances")
        elif value is None:
            reset_fields.add(name)
            replacements[name] = _field_default(name)
        else:
            replacements[name] = value

    changed_fields = frozenset(name for name, value in changes.items() if value is not UNSET)

    return PreparedEngineSettings(
        settings=replace(current, **replacements),
        plugin_additions=plugin_additions,
        changed_fields=changed_fields,
        reset_fields=frozenset(reset_fields),
    )


__all__ = [
    "MAX_PARSE_RECOVERY_ATTEMPTS",
    "SETTING_NAMES",
    "UPDATE_POLICIES",
    "EngineSettings",
    "PreparedEngineSettings",
    "prepare_settings_update",
]

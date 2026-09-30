from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, fields
from types import MappingProxyType
from typing import Any, Final

from interfacy.declarations.executable_flags import ExecutableFlag, normalize_executable_flags
from interfacy.declarations.params import (
    Param,
    ParameterSettingsInput,
    normalize_parameter_settings,
)
from interfacy.declarations.settings import (
    AbbreviationScope,
    validate_abbreviation_scope,
    validate_help_group,
    validate_help_option_sort,
    validate_help_subcommand_sort,
    validate_method_skips,
    validate_model_expansion_max_depth,
)
from interfacy.declarations.sorting import HelpOptionSortRule, HelpSubcommandSortRule


@dataclass(frozen=True, kw_only=True)
class CommandOverrides:
    """
    Per-command overrides of parser-level settings.

    ``None`` inherits the value from the parent command or the parser. Values are
    validated on construction.
    """

    include_inherited_methods: bool | None = None
    include_protected_methods: bool | None = None
    include_private_methods: bool | None = None
    include_staticmethods: bool | None = None
    include_classmethods: bool | None = None
    method_skips: Sequence[str] | None = None
    expand_model_params: bool | None = None
    model_expansion_max_depth: int | None = None
    abbreviation_scope: AbbreviationScope | None = None
    help_option_sort: list[HelpOptionSortRule] | None = None
    help_subcommand_sort: list[HelpSubcommandSortRule] | None = None

    def __post_init__(self) -> None:
        if self.method_skips is not None:
            self._set("method_skips", tuple(validate_method_skips(self.method_skips)))
        if self.model_expansion_max_depth is not None:
            validate_model_expansion_max_depth(self.model_expansion_max_depth)
        if self.abbreviation_scope is not None:
            validate_abbreviation_scope(self.abbreviation_scope)
        self._set("help_option_sort", validate_help_option_sort(self.help_option_sort))
        self._set("help_subcommand_sort", validate_help_subcommand_sort(self.help_subcommand_sort))

    def _set(self, name: str, value: Any) -> None:
        object.__setattr__(self, name, value)


OVERRIDE_NAMES: Final = tuple(override.name for override in fields(CommandOverrides))


@dataclass(frozen=True, kw_only=True)
class CommandOptions(CommandOverrides):
    """Registration options accepted by every ``add_command`` entry point."""

    help_group: str | None = None
    executable_flags: Sequence[ExecutableFlag] = ()
    parameter_settings: Mapping[str, Param] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        super().__post_init__()
        validate_help_group(self.help_group)
        # ``None`` is accepted for both collections, matching the public signatures.
        self._set("executable_flags", tuple(normalize_executable_flags(self.executable_flags)))
        settings: ParameterSettingsInput | None = self.parameter_settings
        self._set("parameter_settings", MappingProxyType(normalize_parameter_settings(settings)))

    @classmethod
    def from_values(cls, values: Mapping[str, Any]) -> CommandOptions:
        """Build options from the entries of ``values`` that name an option."""
        return cls(**{name: values[name] for name in COMMAND_OPTION_NAMES if name in values})

    @property
    def overrides(self) -> CommandOverrides:
        """Return only the setting overrides."""
        return CommandOverrides(**{name: getattr(self, name) for name in OVERRIDE_NAMES})


COMMAND_OPTION_NAMES: Final = tuple(option.name for option in fields(CommandOptions))
DEFAULT_COMMAND_OPTIONS: Final = CommandOptions()


__all__ = [
    "COMMAND_OPTION_NAMES",
    "DEFAULT_COMMAND_OPTIONS",
    "OVERRIDE_NAMES",
    "CommandOptions",
    "CommandOverrides",
]

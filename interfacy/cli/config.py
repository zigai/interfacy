from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, fields
from functools import cache
from importlib import import_module
from pathlib import Path
from typing import Any, TypeVar, cast

from stdl.fs import toml_load

import interfacy.appearance.colors as appearance_colors  # noqa: F401
import interfacy.appearance.layouts as appearance_layouts  # noqa: F401
from interfacy.appearance.help_sort import (
    resolve_help_option_sort_rules,
    resolve_help_subcommand_sort_rules,
)
from interfacy.appearance.layout import HelpLayout, InterfacyColors
from interfacy.exceptions import ConfigurationError
from interfacy.naming.abbreviations import (
    AbbreviationGenerator,
    DefaultAbbreviationGenerator,
    NoAbbreviations,
)
from interfacy.naming.flag_strategy import (
    DefaultFlagStrategy,
    FlagStrategy,
    FlagStyle,
    TranslationMode,
)

_ComponentT = TypeVar("_ComponentT")
_ResolverResultT = TypeVar("_ResolverResultT")
_UNSET = object()

_ABBREVIATION_SCOPE_LOOKUP: dict[str, str] = {
    "topleveloptions": "top_level_options",
    "alloptions": "all_options",
}

_HELP_LAYOUT_ALIASES: dict[str, str] = {
    "default": "interfacy",
    "alignedtype": "alignedtyped",
}

_HELP_COLORS_ALIASES: dict[str, str] = {
    "default": "interfacy",
    "none": "nocolor",
}


def _normalize_name(value: str) -> str:
    return value.replace("-", "").replace("_", "").lower()


@dataclass
class InterfacyConfig:
    help_layout: str | None = field(
        default=None,
        metadata={"section": "appearance", "aliases": ("layout",)},
    )
    help_colors: str | None = field(
        default=None,
        metadata={"section": "appearance", "aliases": ("colors",)},
    )
    flag_strategy: str | None = field(
        default=None,
        metadata={"section": "flags", "aliases": ("strategy",)},
    )
    flag_style: FlagStyle | None = field(
        default=None,
        metadata={"section": "flags", "aliases": ("style",)},
    )
    translation_mode: TranslationMode | None = field(default=None, metadata={"section": "flags"})
    abbreviation_gen: str | None = field(
        default=None,
        metadata={"section": "abbreviations", "aliases": ("generator",)},
    )
    abbreviation_max_generated_len: int | None = field(
        default=None,
        metadata={"section": "abbreviations", "aliases": ("max_generated_len",)},
    )
    abbreviation_scope: str | None = field(
        default=None,
        metadata={"section": "abbreviations", "aliases": ("scope",)},
    )
    help_option_sort: list[str] | None = field(
        default=None,
        metadata={"section": "flags"},
    )
    help_subcommand_sort: list[str] | None = field(
        default=None,
        metadata={"section": "flags"},
    )
    print_result: bool | None = field(
        default=None,
        metadata={"section": "behavior", "passthrough": True},
    )
    full_error_traceback: bool | None = field(
        default=None,
        metadata={"section": "behavior", "passthrough": True},
    )
    tab_completion: bool | None = field(
        default=None,
        metadata={"section": "behavior", "passthrough": True},
    )
    allow_args_from_file: bool | None = field(
        default=None,
        metadata={"section": "behavior", "passthrough": True},
    )
    include_inherited_methods: bool | None = field(
        default=None,
        metadata={"section": "behavior", "passthrough": True},
    )
    include_classmethods: bool | None = field(
        default=None,
        metadata={"section": "behavior", "passthrough": True},
    )
    silent_interrupt: bool | None = field(
        default=None,
        metadata={"section": "behavior", "passthrough": True},
    )


def get_default_config_paths() -> list[Path]:
    env_path = os.environ.get("INTERFACY_CONFIG")
    paths: list[Path] = []
    if env_path:
        paths.append(Path(env_path))
    paths.append(Path.home() / ".config" / "interfacy" / "config.toml")
    return paths


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        return toml_load(path)
    except Exception as exc:
        raise ConfigurationError(f"Invalid TOML in config file: {path}") from exc


def _flatten_config(raw: dict[str, Any]) -> dict[str, Any]:
    data = dict(raw)
    flattened: dict[str, Any] = {}

    for config_field in fields(InterfacyConfig):
        field_name = config_field.name
        if field_name in data:
            flattened[field_name] = data[field_name]
            continue

        section = cast(str | None, config_field.metadata.get("section"))
        if section is None:
            continue
        section_data = data.get(section)
        if not isinstance(section_data, dict):
            continue

        keys = (field_name, *cast(tuple[str, ...], config_field.metadata.get("aliases", ())))
        for key in keys:
            if key in section_data:
                flattened[field_name] = section_data[key]
                break

    return flattened


def load_config(path: Path | None = None) -> InterfacyConfig:
    if path is not None:
        if not path.exists():
            raise FileNotFoundError(path)
        return InterfacyConfig(**_flatten_config(_load_toml(path)))
    for candidate in get_default_config_paths():
        if candidate.exists():
            return InterfacyConfig(**_flatten_config(_load_toml(candidate)))
    return InterfacyConfig()


def _import_symbol(value: str) -> object:
    if ":" not in value:
        raise ConfigurationError(
            f"Invalid import path '{value}'. Use the format 'package.module:Symbol'."
        )
    module_name, symbol_name = value.split(":", 1)
    module = import_module(module_name)
    try:
        return getattr(module, symbol_name)
    except AttributeError as exc:
        raise ConfigurationError(
            f"Config symbol '{symbol_name}' not found in '{module_name}'."
        ) from exc


def _resolve_symbol_value(value: str) -> object:
    symbol = _import_symbol(value)
    return symbol() if isinstance(symbol, type) else symbol


@cache
def _component_registry(
    base_class: type[_ComponentT],
    *,
    include_base: bool = False,
    suffix: str | None = None,
) -> dict[str, type[_ComponentT]]:
    registry: dict[str, type[_ComponentT]] = {}
    seen: set[type[_ComponentT]] = set()
    stack: list[type[_ComponentT]] = [base_class] if include_base else []
    stack.extend(cast(list[type[_ComponentT]], base_class.__subclasses__()))

    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)

        class_name = _normalize_name(current.__name__)
        registry.setdefault(class_name, current)
        if suffix and class_name.endswith(suffix):
            alias = class_name.removesuffix(suffix)
            if alias:
                registry.setdefault(alias, current)

        stack.extend(cast(list[type[_ComponentT]], current.__subclasses__()))

    return registry


def _resolve_named_component(
    value: object,
    *,
    value_name: str,
    component_type: type[_ResolverResultT],
    registry: Mapping[str, type[_ResolverResultT]],
    aliases: Mapping[str, str] | None = None,
) -> _ResolverResultT | None:
    if value is None:
        return None
    if isinstance(value, component_type):
        return value
    if not isinstance(value, str):
        raise ConfigurationError(f"Unknown {value_name} value: {value}")

    if ":" in value:
        resolved = _resolve_symbol_value(value)
        if isinstance(resolved, component_type):
            return resolved
        raise ConfigurationError(
            f"{value_name} symbol must resolve to {component_type.__name__}, got {type(resolved)}"
        )

    key = _normalize_name(value)
    if aliases is not None:
        key = aliases.get(key, key)
    resolved_type = registry.get(key)
    if resolved_type is None:
        raise ConfigurationError(f"Unknown {value_name} value: {value}")
    return resolved_type()


def _resolve_flag_strategy(value: object, config: dict[str, Any]) -> FlagStrategy | None:
    if value is None:
        return None
    if isinstance(value, DefaultFlagStrategy):
        return value
    if callable(getattr(value, "get_arg_flags", None)):
        return cast(FlagStrategy, value)
    if not isinstance(value, str):
        raise ConfigurationError(f"Unknown flag_strategy value: {value}")
    if ":" in value:
        return cast(FlagStrategy, _resolve_symbol_value(value))
    if _normalize_name(value) in {"default", "standard"}:
        return DefaultFlagStrategy(
            style=config.get("flag_style") or "required_positional",
            translation_mode=config.get("translation_mode") or "kebab",
        )
    raise ConfigurationError(f"Unknown flag_strategy value: {value}")


def _resolve_abbreviation_max_generated_len(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigurationError("abbreviation_max_generated_len must be an integer >= 1")
    return value


def _resolve_abbreviation_gen(
    value: object,
    config: dict[str, Any],
) -> AbbreviationGenerator | None:
    max_generated_len = _resolve_abbreviation_max_generated_len(
        config.get("abbreviation_max_generated_len")
    )
    if value is None:
        if max_generated_len is None:
            return None
        return DefaultAbbreviationGenerator(max_generated_len=max_generated_len)
    if isinstance(value, AbbreviationGenerator):
        return value
    if not isinstance(value, str):
        raise ConfigurationError(f"Unknown abbreviation_gen value: {value}")
    if ":" in value:
        resolved = _resolve_symbol_value(value)
        if isinstance(resolved, AbbreviationGenerator):
            return resolved
        raise ConfigurationError(
            f"abbreviation_gen symbol must resolve to AbbreviationGenerator, got {type(resolved)}"
        )
    key = _normalize_name(value)
    if key in {"default", "standard"}:
        return DefaultAbbreviationGenerator(max_generated_len=max_generated_len or 1)
    if key in {"none", "noabbrev", "noabbreviations"}:
        return NoAbbreviations()
    raise ConfigurationError(f"Unknown abbreviation_gen value: {value}")


def _resolve_abbreviation_scope(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigurationError("abbreviation_scope must be a string")
    resolved = _ABBREVIATION_SCOPE_LOOKUP.get(_normalize_name(value))
    if resolved is None:
        raise ConfigurationError(
            "abbreviation_scope must be one of: top_level_options, all_options"
        )
    return resolved


def _resolve_default_for_field(
    field_name: str,
    value: object,
    config_data: dict[str, Any],
) -> object:
    resolved: object = _UNSET

    if field_name == "help_layout":
        resolved = _resolve_named_component(
            value,
            value_name="help_layout",
            component_type=HelpLayout,
            registry=_component_registry(HelpLayout, suffix="layout"),
            aliases=_HELP_LAYOUT_ALIASES,
        )
    elif field_name == "help_colors":
        resolved = _resolve_named_component(
            value,
            value_name="help_colors",
            component_type=InterfacyColors,
            registry=_component_registry(
                InterfacyColors,
                include_base=True,
                suffix="colors",
            ),
            aliases=_HELP_COLORS_ALIASES,
        )
    elif field_name == "flag_strategy":
        resolved = _resolve_flag_strategy(value, config_data)
    elif field_name == "abbreviation_gen":
        resolved = _resolve_abbreviation_gen(value, config_data)
    elif field_name == "abbreviation_max_generated_len":
        resolved = _resolve_abbreviation_max_generated_len(value)
    elif field_name == "abbreviation_scope":
        resolved = _resolve_abbreviation_scope(value)
    elif field_name == "help_option_sort":
        resolved = resolve_help_option_sort_rules(value, value_name="help_option_sort")
    elif field_name == "help_subcommand_sort":
        resolved = resolve_help_subcommand_sort_rules(value, value_name="help_subcommand_sort")

    return resolved


def apply_config_defaults(
    config: InterfacyConfig | dict[str, Any],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    if isinstance(config, InterfacyConfig):
        config_data = asdict(config)
    elif isinstance(config, dict):
        config_data = dict(config)
    else:
        raise ConfigurationError(f"Unsupported config type: {type(config)}")

    resolved = dict(overrides)

    for config_field in fields(InterfacyConfig):
        field_name = config_field.name
        if resolved.get(field_name) is not None:
            continue

        value = config_data.get(field_name)
        default_value = _resolve_default_for_field(field_name, value, config_data)
        if default_value is not _UNSET:
            resolved[field_name] = default_value
            continue

        if (
            cast(bool, config_field.metadata.get("passthrough", False))
            and field_name in config_data
        ):
            resolved[field_name] = value

    return resolved


__all__ = ["InterfacyConfig", "apply_config_defaults", "get_default_config_paths", "load_config"]

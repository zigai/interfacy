from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, fields
from functools import cache
from importlib import import_module
from pathlib import Path
from typing import Any, TypeGuard, TypeVar

from platformdirs import user_config_path
from stdl.fs import toml_load

import interfacy.help.layouts as appearance_layouts
from interfacy.declarations.settings import BACKEND_NAMES, AbbreviationScope, BackendName
from interfacy.engine import UNSET
from interfacy.engine.settings import SETTING_NAMES, EngineSettings
from interfacy.exceptions import ConfigurationError
from interfacy.help import HelpLayout
from interfacy.help.colors import InterfacyColors
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
from interfacy.plugins import InterfacyPlugin

_ComponentT = TypeVar("_ComponentT")
_ResolverResultT = TypeVar("_ResolverResultT")
Backend = BackendName

_ABBREVIATION_SCOPE_LOOKUP: dict[str, AbbreviationScope] = {
    "topleveloptions": "top_level_options",
    "alloptions": "all_options",
}


def _normalize_name(value: str) -> str:
    return value.replace("-", "").replace("_", "").lower()


@dataclass
class InterfacyConfig:
    """Configuration values loaded for the Interfacy CLI entrypoint."""

    backend: Backend | None = field(default=None, metadata={"section": "behavior"})
    help_layout: str | None = field(
        default=None,
        metadata={"section": "appearance", "key": "layout"},
    )
    help_colors: str | None = field(
        default=None,
        metadata={"section": "appearance", "key": "colors"},
    )
    flag_strategy: str | None = field(
        default=None,
        metadata={"section": "flags", "key": "strategy"},
    )
    flag_style: FlagStyle | None = field(
        default=None,
        metadata={"section": "flags", "key": "style"},
    )
    translation_mode: TranslationMode | None = field(default=None, metadata={"section": "flags"})
    abbreviation_gen: str | None = field(
        default=None,
        metadata={"section": "abbreviations", "key": "generator"},
    )
    abbreviation_max_generated_len: int | None = field(
        default=None,
        metadata={"section": "abbreviations", "key": "max_generated_len"},
    )
    abbreviation_scope: str | None = field(
        default=None,
        metadata={"section": "abbreviations", "key": "scope"},
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
        metadata={"section": "behavior"},
    )
    full_error_traceback: bool | None = field(
        default=None,
        metadata={"section": "behavior"},
    )
    tab_completion: bool | None = field(
        default=None,
        metadata={"section": "behavior"},
    )
    allow_args_from_file: bool | None = field(
        default=None,
        metadata={"section": "behavior"},
    )
    include_inherited_methods: bool | None = field(
        default=None,
        metadata={"section": "behavior"},
    )
    include_protected_methods: bool | None = field(
        default=None,
        metadata={"section": "behavior"},
    )
    include_private_methods: bool | None = field(
        default=None,
        metadata={"section": "behavior"},
    )
    include_staticmethods: bool | None = field(
        default=None,
        metadata={"section": "behavior"},
    )
    include_classmethods: bool | None = field(
        default=None,
        metadata={"section": "behavior"},
    )
    method_skips: list[str] | None = field(
        default=None,
        metadata={"section": "behavior"},
    )
    silent_interrupt: bool | None = field(
        default=None,
        metadata={"section": "behavior"},
    )
    expand_model_params: bool | None = field(
        default=None,
        metadata={"section": "behavior"},
    )
    model_expansion_max_depth: int | None = field(
        default=None,
        metadata={"section": "behavior"},
    )
    parse_recovery_max_attempts: int | None = field(
        default=None,
        metadata={"section": "behavior"},
    )
    bool_negative_prefix: str | None = field(
        default=None,
        metadata={"section": "flags"},
    )
    help_flags: list[str] | None = field(
        default=None,
        metadata={"section": "flags"},
    )
    plugins: list[str] | None = field(
        default=None,
        metadata={"section": "plugins", "key": "enabled"},
    )


def get_default_config_paths() -> list[Path]:
    env_path = os.environ.get("INTERFACY_CONFIG")
    paths: list[Path] = []
    if env_path:
        paths.append(Path(env_path))

    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if xdg_config_home:
        paths.append(Path(xdg_config_home) / "interfacy" / "config.toml")
    elif sys.platform != "win32":
        paths.append(Path.home() / ".config" / "interfacy" / "config.toml")
    else:
        paths.append(user_config_path("interfacy", appauthor=False) / "config.toml")

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
        section_value = config_field.metadata.get("section")
        if section_value is not None and not isinstance(section_value, str):
            raise ConfigurationError(f"Invalid config section metadata for {field_name}")

        section = section_value
        key_value = config_field.metadata.get("key", field_name)
        if not isinstance(key_value, str):
            raise ConfigurationError(f"Invalid config key metadata for {field_name}")

        key = key_value
        section_data = data.get(section) if section is not None else None

        if section is None:
            continue

        if not isinstance(section_data, dict):
            continue

        if key in section_data:
            flattened[field_name] = section_data[key]

    return flattened


def load_config(path: Path | None = None) -> InterfacyConfig:
    """Load CLI configuration from an explicit path or the default search locations."""
    if path is not None:
        if not path.exists():
            raise FileNotFoundError(path)

        return InterfacyConfig(**_flatten_config(_load_toml(path)))

    for candidate in get_default_config_paths():
        if candidate.exists():
            return InterfacyConfig(**_flatten_config(_load_toml(candidate)))

    return InterfacyConfig()


def _import_symbol(value: str) -> Any:
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


def _resolve_symbol_value(value: str) -> Any:
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
    stack.extend(base_class.__subclasses__())

    while stack:
        current = stack.pop()
        if current in seen:
            continue

        seen.add(current)
        stack.extend(current.__subclasses__())
        if (
            current.__module__.startswith(f"{appearance_layouts.__name__}.")
            and current.__name__ not in appearance_layouts.__all__
        ):
            continue

        class_name = _normalize_name(current.__name__)
        registry.setdefault(class_name, current)

        if suffix and class_name.endswith(suffix):
            alias = class_name.removesuffix(suffix)
            if alias:
                registry.setdefault(alias, current)

    return registry


def _resolve_named_component(
    value: Any,
    *,
    value_name: str,
    component_type: type[_ResolverResultT],
    registry: dict[str, type[_ResolverResultT]],
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
    resolved_type = registry.get(key)
    if resolved_type is None:
        raise ConfigurationError(f"Unknown {value_name} value: {value}")

    return resolved_type()


def _is_flag_strategy(value: Any) -> TypeGuard[FlagStrategy]:
    return isinstance(value, FlagStrategy) or callable(getattr(value, "get_arg_flags", None))


def _resolve_flag_strategy(value: Any, config: dict[str, Any]) -> FlagStrategy | None:
    if value is None:
        return None

    if isinstance(value, DefaultFlagStrategy):
        return value

    if _is_flag_strategy(value):
        return value

    if not isinstance(value, str):
        raise ConfigurationError(f"Unknown flag_strategy value: {value}")

    if ":" in value:
        resolved = _resolve_symbol_value(value)
        if _is_flag_strategy(resolved):
            return resolved

        raise ConfigurationError("flag_strategy symbol must resolve to a flag strategy")

    if _normalize_name(value) in {"default", "standard"}:
        return DefaultFlagStrategy(
            style=config.get("flag_style") or "required_positional",
            translation_mode=config.get("translation_mode") or "kebab",
        )

    raise ConfigurationError(f"Unknown flag_strategy value: {value}")


def _resolve_abbreviation_gen(value: Any, config: dict[str, Any]) -> AbbreviationGenerator:
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
        max_generated_len = config.get("abbreviation_max_generated_len") or 1
        return DefaultAbbreviationGenerator(max_generated_len=max_generated_len)
    if key in {"none", "noabbrev", "noabbreviations"}:
        return NoAbbreviations()

    raise ConfigurationError(f"Unknown abbreviation_gen value: {value}")


def _resolve_abbreviation_scope(value: Any) -> AbbreviationScope:
    if not isinstance(value, str):
        raise ConfigurationError("abbreviation_scope must be a string")

    resolved = _ABBREVIATION_SCOPE_LOOKUP.get(_normalize_name(value))
    if resolved is None:
        raise ConfigurationError(
            "abbreviation_scope must be one of: top_level_options, all_options"
        )

    return resolved


def _resolve_backend(value: Any) -> Backend:
    if not isinstance(value, str):
        raise ConfigurationError("backend must be a string")

    for name in BACKEND_NAMES:
        if _normalize_name(value) == name:
            return name

    raise ConfigurationError(f"backend must be one of: {', '.join(BACKEND_NAMES)}")


def _resolve_plugin(value: Any) -> InterfacyPlugin:
    if isinstance(value, InterfacyPlugin):
        return value
    if not isinstance(value, str):
        raise ConfigurationError(f"Plugin entries must be import paths, got {value!r}")

    resolved = _resolve_symbol_value(value)
    if not isinstance(resolved, InterfacyPlugin):
        raise ConfigurationError(
            f"Plugin symbol must resolve to InterfacyPlugin, got {type(resolved)}"
        )

    return resolved


def _resolve_plugins(value: Any) -> list[InterfacyPlugin]:
    if not isinstance(value, list):
        raise ConfigurationError("plugins.enabled must be a list")

    return [_resolve_plugin(item) for item in value]


# Config values that name objects rather than hold them. Every other value is passed through,
# and those that are engine settings are validated by EngineSettings.
_RESOLVERS: dict[str, Callable[[Any, dict[str, Any]], Any]] = {
    "backend": lambda value, _config: _resolve_backend(value),
    "help_layout": lambda value, _config: _resolve_named_component(
        value,
        value_name="help_layout",
        component_type=HelpLayout,
        registry=_component_registry(HelpLayout, suffix="layout"),
    ),
    "help_colors": lambda value, _config: _resolve_named_component(
        value,
        value_name="help_colors",
        component_type=InterfacyColors,
        registry=_component_registry(InterfacyColors, include_base=True, suffix="colors"),
    ),
    "flag_strategy": _resolve_flag_strategy,
    "abbreviation_gen": _resolve_abbreviation_gen,
    "abbreviation_scope": lambda value, _config: _resolve_abbreviation_scope(value),
    "plugins": lambda value, _config: _resolve_plugins(value),
}
# Config keys consumed while resolving other values.
_CONFIG_ONLY_FIELDS = frozenset({"flag_style", "translation_mode"})


def apply_config_defaults(
    config: InterfacyConfig | dict[str, Any],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    """
    Merge validated config-derived defaults into a dictionary of explicit parser overrides.

    Raises:
        ConfigurationError: If a config value is invalid.
    """
    if isinstance(config, InterfacyConfig):
        config_data = asdict(config)
    elif isinstance(config, dict):
        config_data = dict(config)
    else:
        raise ConfigurationError(f"Unsupported config type: {type(config)}")

    resolved = {name: value for name, value in overrides.items() if value is not UNSET}
    defaults: dict[str, Any] = {}
    for config_field in fields(InterfacyConfig):
        name = config_field.name
        value = config_data.get(name)
        if name in resolved or name in _CONFIG_ONLY_FIELDS or value is None:
            continue

        resolver = _RESOLVERS.get(name)
        defaults[name] = value if resolver is None else resolver(value, config_data)

    settings = {name: value for name, value in defaults.items() if name in SETTING_NAMES}
    validated = EngineSettings(**settings)
    defaults.update({name: getattr(validated, name) for name in settings})

    return {**resolved, **defaults}


__all__ = ["InterfacyConfig", "apply_config_defaults", "get_default_config_paths", "load_config"]

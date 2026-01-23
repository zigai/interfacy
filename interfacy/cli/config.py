from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

from interfacy.appearance.colors import Aurora, NoColor
from interfacy.appearance.layout import HelpLayout, InterfacyColors
from interfacy.appearance.layouts import (
    Aligned,
    AlignedTyped,
    ArgparseLayout,
    ClapLayout,
    InterfacyLayout,
    Modern,
)
from interfacy.exceptions import ConfigurationError
from interfacy.naming.abbreviations import DefaultAbbreviationGenerator, NoAbbreviations
from interfacy.naming.flag_strategy import (
    DefaultFlagStrategy,
    FlagStrategy,
    FlagStyle,
    TranslationMode,
)

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


@dataclass
class InterfacyConfig:
    help_layout: str | None = None
    help_colors: str | None = None
    flag_strategy: str | None = None
    flag_style: FlagStyle | None = None
    translation_mode: TranslationMode | None = None
    abbreviation_gen: str | None = None
    abbreviation_min_len: int | None = None
    print_result: bool | None = None
    full_error_traceback: bool | None = None
    tab_completion: bool | None = None
    allow_args_from_file: bool | None = None
    include_inherited_methods: bool | None = None
    include_classmethods: bool | None = None
    silent_interrupt: bool | None = None


def _normalize_name(value: str) -> str:
    return value.replace("-", "").replace("_", "").lower()


def _default_config_paths() -> list[Path]:
    env_path = os.environ.get("INTERFACY_CONFIG")
    paths = []
    if env_path:
        paths.append(Path(env_path))
    paths.append(Path.cwd() / ".interfacy.toml")
    paths.append(Path.home() / ".config" / "interfacy" / "config.toml")
    return paths


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigurationError(f"Invalid TOML in config file: {path}") from exc


def _coerce_config(raw: dict[str, Any]) -> InterfacyConfig:
    data = dict(raw)
    appearance = data.get("appearance")
    if isinstance(appearance, dict):
        data.setdefault("help_layout", appearance.get("layout"))
        data.setdefault("help_colors", appearance.get("colors"))

    flags = data.get("flags")
    if isinstance(flags, dict):
        data.setdefault("flag_strategy", flags.get("strategy"))
        data.setdefault("flag_style", flags.get("style"))
        data.setdefault("translation_mode", flags.get("translation_mode"))

    abbreviations = data.get("abbreviations")
    if isinstance(abbreviations, dict):
        data.setdefault("abbreviation_gen", abbreviations.get("generator"))
        data.setdefault("abbreviation_min_len", abbreviations.get("min_len"))

    behavior = data.get("behavior")
    if isinstance(behavior, dict):
        data.setdefault("print_result", behavior.get("print_result"))
        data.setdefault("full_error_traceback", behavior.get("full_error_traceback"))
        data.setdefault("tab_completion", behavior.get("tab_completion"))
        data.setdefault("allow_args_from_file", behavior.get("allow_args_from_file"))
        data.setdefault("include_inherited_methods", behavior.get("include_inherited_methods"))
        data.setdefault("include_classmethods", behavior.get("include_classmethods"))
        data.setdefault("silent_interrupt", behavior.get("silent_interrupt"))
    return InterfacyConfig(
        **{k: v for k, v in data.items() if k in InterfacyConfig.__annotations__}
    )


def load_config(path: Path | None = None) -> InterfacyConfig:
    if path is not None:
        if not path.exists():
            raise FileNotFoundError(path)
        return _coerce_config(_load_toml(path))

    for candidate in _default_config_paths():
        if candidate.exists():
            return _coerce_config(_load_toml(candidate))
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


def _resolve_help_layout(value: Any) -> HelpLayout | None:
    if value is None:
        return None
    if isinstance(value, HelpLayout):
        return value
    if isinstance(value, str):
        if ":" in value:
            symbol = _import_symbol(value)
            return symbol() if isinstance(symbol, type) else symbol
        lookup = {
            "default": InterfacyLayout,
            "interfacy": InterfacyLayout,
            "aligned": Aligned,
            "alignedtyped": AlignedTyped,
            "alignedtype": AlignedTyped,
            "modern": Modern,
            "argparse": ArgparseLayout,
            "clap": ClapLayout,
        }
        key = _normalize_name(value)
        if key in lookup:
            return lookup[key]()
    raise ConfigurationError(f"Unknown help_layout value: {value}")


def _resolve_help_colors(value: Any) -> InterfacyColors | None:
    if value is None:
        return None
    if isinstance(value, InterfacyColors):
        return value
    if isinstance(value, str):
        if ":" in value:
            symbol = _import_symbol(value)
            return symbol() if isinstance(symbol, type) else symbol
        lookup = {
            "default": InterfacyColors,
            "interfacy": InterfacyColors,
            "aurora": Aurora,
            "nocolor": NoColor,
            "none": NoColor,
        }
        key = _normalize_name(value)
        if key in lookup:
            return lookup[key]()
    raise ConfigurationError(f"Unknown help_colors value: {value}")


def _resolve_flag_strategy(value: Any, config: dict[str, Any]) -> FlagStrategy | None:
    if value is None:
        return None
    if isinstance(value, DefaultFlagStrategy):
        return value
    if callable(getattr(value, "get_arg_flags", None)):
        return value
    if isinstance(value, str):
        if ":" in value:
            symbol = _import_symbol(value)
            return symbol() if isinstance(symbol, type) else symbol
        key = _normalize_name(value)
        if key in {"default", "standard"}:
            style = config.get("flag_style")
            translation_mode = config.get("translation_mode")
            return DefaultFlagStrategy(
                style=style or "required_positional",
                translation_mode=translation_mode or "kebab",
            )
    raise ConfigurationError(f"Unknown flag_strategy value: {value}")


def _resolve_abbreviation_gen(value: Any, config: dict[str, Any]) -> Any | None:
    if value is None:
        return None
    if isinstance(value, (DefaultAbbreviationGenerator, NoAbbreviations)):
        return value
    if isinstance(value, str):
        if ":" in value:
            symbol = _import_symbol(value)
            return symbol() if isinstance(symbol, type) else symbol
        key = _normalize_name(value)
        if key in {"default", "standard"}:
            min_len = config.get("abbreviation_min_len")
            return DefaultAbbreviationGenerator(min_len=min_len or 3)
        if key in {"none", "noabbrev", "noabbreviations"}:
            return NoAbbreviations()
    raise ConfigurationError(f"Unknown abbreviation_gen value: {value}")


def _to_config_dict(config: InterfacyConfig | dict[str, Any]) -> dict[str, Any]:
    if isinstance(config, InterfacyConfig):
        return asdict(config)
    if isinstance(config, dict):
        return dict(config)
    raise ConfigurationError(f"Unsupported config type: {type(config)}")


def apply_config_defaults(
    config: InterfacyConfig | dict[str, Any],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    cfg = _to_config_dict(config)
    resolved = dict(overrides)

    if overrides.get("help_layout") is None:
        resolved["help_layout"] = _resolve_help_layout(cfg.get("help_layout"))

    if overrides.get("help_colors") is None:
        resolved["help_colors"] = _resolve_help_colors(cfg.get("help_colors"))

    if overrides.get("flag_strategy") is None:
        resolved["flag_strategy"] = _resolve_flag_strategy(cfg.get("flag_strategy"), cfg)

    if overrides.get("abbreviation_gen") is None:
        resolved["abbreviation_gen"] = _resolve_abbreviation_gen(cfg.get("abbreviation_gen"), cfg)

    passthrough_keys = [
        "print_result",
        "full_error_traceback",
        "tab_completion",
        "allow_args_from_file",
        "include_inherited_methods",
        "include_classmethods",
        "silent_interrupt",
    ]
    for key in passthrough_keys:
        if overrides.get(key) is None and key in cfg:
            resolved[key] = cfg.get(key)

    return resolved

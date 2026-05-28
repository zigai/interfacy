from __future__ import annotations

from pathlib import Path

import pytest

from interfacy.appearance.colors import Aurora
from interfacy.appearance.layouts import InterfacyLayout, Modern
from interfacy.cli.config import apply_config_defaults, load_config
from interfacy.exceptions import ConfigurationError
from interfacy.naming.abbreviations import DefaultAbbreviationGenerator
from interfacy.naming.flag_strategy import DefaultFlagStrategy
from interfacy.plugins import InterfacyPlugin


def test_load_config_and_apply_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "[appearance]",
                'layout = "modern"',
                'colors = "aurora"',
                "",
                "[flags]",
                'strategy = "default"',
                'style = "keyword_only"',
                'translation_mode = "snake"',
                'help_option_sort = ["bool_last", "alphabetical"]',
                'help_subcommand_sort = ["name_length_desc"]',
                'bool_negative_prefix = "without-"',
                "",
                "[abbreviations]",
                'generator = "default"',
                "max_generated_len = 2",
                'scope = "all_options"',
                "",
                "[behavior]",
                'backend = "argparse"',
                "print_result = true",
                "include_protected_methods = true",
                "include_private_methods = true",
                "include_staticmethods = false",
                'method_skips = ["close", "setup", "close"]',
                "expand_model_params = false",
                "model_expansion_max_depth = 2",
                "parse_recovery_max_attempts = 4",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    config = load_config(config_path)
    overrides = apply_config_defaults(
        config,
        {
            "help_layout": None,
            "help_colors": None,
            "flag_strategy": None,
            "abbreviation_gen": None,
            "abbreviation_max_generated_len": None,
            "abbreviation_scope": None,
            "help_option_sort": None,
            "help_subcommand_sort": None,
            "print_result": None,
            "full_error_traceback": None,
            "tab_completion": None,
            "allow_args_from_file": None,
            "include_inherited_methods": None,
            "include_protected_methods": None,
            "include_private_methods": None,
            "include_staticmethods": None,
            "include_classmethods": None,
            "method_skips": None,
            "silent_interrupt": None,
            "expand_model_params": None,
            "model_expansion_max_depth": None,
            "parse_recovery_max_attempts": None,
            "bool_negative_prefix": None,
            "backend": None,
        },
    )

    assert isinstance(overrides["help_layout"], Modern)
    assert isinstance(overrides["help_colors"], Aurora)
    assert isinstance(overrides["flag_strategy"], DefaultFlagStrategy)
    assert overrides["flag_strategy"].style == "keyword_only"
    assert overrides["flag_strategy"].translation_mode == "snake"
    assert isinstance(overrides["abbreviation_gen"], DefaultAbbreviationGenerator)
    assert overrides["abbreviation_gen"].max_generated_len == 2
    assert overrides["abbreviation_max_generated_len"] == 2
    assert overrides["abbreviation_scope"] == "all_options"
    assert overrides["help_option_sort"] == ["bool_last", "alphabetical"]
    assert overrides["help_subcommand_sort"] == ["name_length_desc"]
    assert overrides["print_result"] is True
    assert overrides["backend"] == "argparse"
    assert overrides["include_protected_methods"] is True
    assert overrides["include_private_methods"] is True
    assert overrides["include_staticmethods"] is False
    assert overrides["method_skips"] == ["close", "setup"]
    assert overrides["expand_model_params"] is False
    assert overrides["model_expansion_max_depth"] == 2
    assert overrides["parse_recovery_max_attempts"] == 4
    assert overrides["bool_negative_prefix"] == "without-"


def test_apply_config_defaults_respects_overrides(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[appearance]\nlayout = "modern"\n', encoding="utf-8")

    config = load_config(config_path)
    override_layout = InterfacyLayout()
    overrides = apply_config_defaults(
        config,
        {
            "help_layout": override_layout,
            "help_colors": None,
            "flag_strategy": None,
            "abbreviation_gen": None,
            "abbreviation_max_generated_len": None,
            "abbreviation_scope": None,
            "help_option_sort": None,
            "help_subcommand_sort": None,
            "print_result": None,
            "full_error_traceback": None,
            "tab_completion": None,
            "allow_args_from_file": None,
            "include_inherited_methods": None,
            "include_classmethods": None,
            "silent_interrupt": None,
            "expand_model_params": None,
            "model_expansion_max_depth": None,
            "bool_negative_prefix": None,
            "backend": None,
        },
    )

    assert overrides["help_layout"] is override_layout


def test_load_config_rejects_string_help_option_sort(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "[flags]",
                'help_option_sort = "alphabetical"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    with pytest.raises(ConfigurationError, match="help_option_sort must be a list"):
        apply_config_defaults(
            config,
            {
                "help_layout": None,
                "help_colors": None,
                "flag_strategy": None,
                "abbreviation_gen": None,
                "abbreviation_max_generated_len": None,
                "abbreviation_scope": None,
                "help_option_sort": None,
                "help_subcommand_sort": None,
                "print_result": None,
                "full_error_traceback": None,
                "tab_completion": None,
                "allow_args_from_file": None,
                "include_inherited_methods": None,
                "include_classmethods": None,
                "silent_interrupt": None,
                "expand_model_params": None,
                "model_expansion_max_depth": None,
                "bool_negative_prefix": None,
                "backend": None,
            },
        )


def test_load_config_rejects_string_help_subcommand_sort(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "[flags]",
                'help_subcommand_sort = "alphabetical"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    with pytest.raises(ConfigurationError, match="help_subcommand_sort must be a list"):
        apply_config_defaults(
            config,
            {
                "help_layout": None,
                "help_colors": None,
                "flag_strategy": None,
                "abbreviation_gen": None,
                "abbreviation_max_generated_len": None,
                "abbreviation_scope": None,
                "help_option_sort": None,
                "help_subcommand_sort": None,
                "print_result": None,
                "full_error_traceback": None,
                "tab_completion": None,
                "allow_args_from_file": None,
                "include_inherited_methods": None,
                "include_classmethods": None,
                "silent_interrupt": None,
                "expand_model_params": None,
                "model_expansion_max_depth": None,
                "bool_negative_prefix": None,
                "backend": None,
            },
        )


def test_load_config_ignores_top_level_fields(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                'help_layout = "clap"',
                "",
                "[appearance]",
                'layout = "modern"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    overrides = apply_config_defaults(config, {"help_layout": None})
    assert isinstance(overrides["help_layout"], Modern)


def test_load_config_rejects_legacy_layout_value_alias(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[appearance]\nlayout = "alignedtype"\n', encoding="utf-8")

    config = load_config(config_path)
    with pytest.raises(ConfigurationError, match="Unknown help_layout value"):
        apply_config_defaults(config, {"help_layout": None})


def test_load_config_rejects_default_color_value_alias(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[appearance]\ncolors = "default"\n', encoding="utf-8")

    config = load_config(config_path)
    with pytest.raises(ConfigurationError, match="Unknown help_colors value"):
        apply_config_defaults(config, {"help_colors": None})


def test_load_config_resolves_plugin_import_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plugin_module = tmp_path / "plugin_config_mod.py"
    plugin_module.write_text(
        "\n".join(
            [
                "from interfacy.plugins import InterfacyPlugin",
                "",
                "class ConfiguredPlugin(InterfacyPlugin):",
                "    name = 'configured'",
                "",
                "class InstancePlugin(InterfacyPlugin):",
                "    name = 'instance'",
                "",
                "plugin_instance = InstancePlugin()",
                "",
            ]
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "[plugins]",
                (
                    'enabled = ["plugin_config_mod:ConfiguredPlugin", '
                    '"plugin_config_mod:plugin_instance"]'
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    config = load_config(config_path)
    overrides = apply_config_defaults(config, {"plugins": None})

    assert [plugin.plugin_name for plugin in overrides["plugins"]] == ["configured", "instance"]
    assert all(isinstance(plugin, InterfacyPlugin) for plugin in overrides["plugins"])


def test_load_config_rejects_non_plugin_symbol(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plugin_module = tmp_path / "plugin_non_plugin_mod.py"
    plugin_module.write_text("not_a_plugin = object()\n", encoding="utf-8")
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "[plugins]",
                'enabled = ["plugin_non_plugin_mod:not_a_plugin"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    config = load_config(config_path)
    with pytest.raises(ConfigurationError, match="Plugin symbol must resolve"):
        apply_config_defaults(config, {"plugins": None})

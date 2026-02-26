from __future__ import annotations

from pathlib import Path

import pytest

from interfacy.appearance.colors import Aurora
from interfacy.appearance.layouts import InterfacyLayout, Modern
from interfacy.cli.config import apply_config_defaults, load_config
from interfacy.exceptions import ConfigurationError
from interfacy.naming.abbreviations import DefaultAbbreviationGenerator
from interfacy.naming.flag_strategy import DefaultFlagStrategy


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
                "",
                "[abbreviations]",
                'generator = "default"',
                "max_generated_len = 2",
                'scope = "all_options"',
                "",
                "[behavior]",
                "print_result = true",
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
            "print_result": None,
            "full_error_traceback": None,
            "tab_completion": None,
            "allow_args_from_file": None,
            "include_inherited_methods": None,
            "include_classmethods": None,
            "silent_interrupt": None,
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
    assert overrides["print_result"] is True


def test_apply_config_defaults_respects_overrides(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('help_layout = "modern"\n', encoding="utf-8")

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
            "print_result": None,
            "full_error_traceback": None,
            "tab_completion": None,
            "allow_args_from_file": None,
            "include_inherited_methods": None,
            "include_classmethods": None,
            "silent_interrupt": None,
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
                "print_result": None,
                "full_error_traceback": None,
                "tab_completion": None,
                "allow_args_from_file": None,
                "include_inherited_methods": None,
                "include_classmethods": None,
                "silent_interrupt": None,
            },
        )

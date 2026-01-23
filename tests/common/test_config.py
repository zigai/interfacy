from __future__ import annotations

from pathlib import Path

from interfacy.appearance.colors import Aurora
from interfacy.appearance.layouts import InterfacyLayout, Modern
from interfacy.cli.config import apply_config_defaults, load_config
from interfacy.naming.abbreviations import NoAbbreviations
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
                "",
                "[abbreviations]",
                'generator = "none"',
                "min_len = 5",
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
    assert isinstance(overrides["abbreviation_gen"], NoAbbreviations)
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

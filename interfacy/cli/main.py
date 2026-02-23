from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any

from interfacy.appearance.layout import HelpLayout
from interfacy.appearance.layouts import InterfacyLayout
from interfacy.argparse_backend.argparser import Argparser
from interfacy.argparse_backend.argument_parser import ArgumentParser
from interfacy.cli.config import apply_config_defaults, load_config
from interfacy.core import ExitCode, InterfacyParser
from interfacy.naming.abbreviations import DefaultAbbreviationGenerator


def _get_version() -> str:
    try:
        return version("interfacy")
    except PackageNotFoundError:
        return "unknown"


def _default_config_paths() -> list[Path]:
    env_path = os.environ.get("INTERFACY_CONFIG")
    paths: list[Path] = []
    if env_path:
        paths.append(Path(env_path))
    paths.append(Path.home() / ".config" / "interfacy" / "config.toml")
    return paths


def _split_target(target: str) -> tuple[str, str]:
    if ":" not in target:
        raise ValueError(
            "Target must be in the form 'module:object' or 'path.py:object'. "
            f"Got: '{target}'. Example: 'main.py:main'."
        )
    # Use rsplit to preserve Windows drive letters (e.g. C:\path\mod.py:symbol).
    module_ref, symbol_ref = target.rsplit(":", 1)
    if not module_ref or not symbol_ref:
        raise ValueError(
            "Target must include both module/path and symbol. "
            f"Got: '{target}'. Example: 'main.py:main'."
        )
    return module_ref, symbol_ref


def _load_module_from_path(path: Path) -> ModuleType:
    module_name = f"interfacy_entry_{path.stem}_{abs(hash(str(path)))}"
    spec = spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from path: {path}")
    module = module_from_spec(spec)
    sys.modules[module_name] = module
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec.loader.exec_module(module)
    return module


def _load_module(module_ref: str) -> ModuleType:
    path = Path(module_ref)
    if module_ref.endswith(".py") or path.exists():
        if not path.exists():
            raise FileNotFoundError(f"Python file not found: {path}")
        if path.is_dir():
            raise ValueError(f"Expected a Python file, got directory: {path}")
        return _load_module_from_path(path)
    return import_module(module_ref)


def _resolve_symbol(module: ModuleType, symbol_ref: str) -> object:
    current: object = module
    for part in symbol_ref.split("."):
        if not hasattr(current, part):
            raise AttributeError(f"Symbol '{symbol_ref}' not found in module '{module.__name__}'.")
        current = getattr(current, part)
    return current


def resolve_target(target: str) -> object:
    """
    Resolve a module or file target to a Python object.

    Args:
        target (str): Target spec "module:object" or "path.py:object".
    """
    module_ref, symbol_ref = _split_target(target)
    module = _load_module(module_ref)
    return _resolve_symbol(module, symbol_ref)


def resolve_entrypoint_settings() -> dict[str, Any]:
    """Return config-derived defaults for the CLI entrypoint."""
    return apply_config_defaults(
        load_config(),
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


def _resolve_help_layout(settings: dict[str, Any]) -> InterfacyLayout:
    help_layout = settings.get("help_layout") or InterfacyLayout()
    help_colors = settings.get("help_colors")
    if help_colors is not None:
        help_layout.style = help_colors
    return help_layout


def build_parser(settings: dict[str, Any]) -> ArgumentParser:
    """
    Build the entrypoint ArgumentParser for the Interfacy CLI.

    Args:
        settings (dict[str, Any]): Resolved configuration settings.
    """
    description = (
        "Interfacy is a CLI framework for building command-line interfaces from Python callables."
    )
    epilog = "Use 'interfacy TARGET --help' to display the help text for the target.\n\n"

    parser = ArgumentParser(
        prog="interfacy",
        description=description,
        epilog=epilog,
        help_layout=_resolve_help_layout(settings),
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Python file or module with a symbol (e.g. main.py:main or pkg.cli:app).",
    )
    parser.add_argument(
        "ARGS",
        nargs=argparse.REMAINDER,
        help="Arguments passed through to the target command.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"interfacy {_get_version()}",
        help="show version and exit.",
    )
    parser.add_argument(
        "--config-paths",
        action="store_true",
        help="print config file search paths and exit.",
    )
    return parser


def build_runner_kwargs(settings: dict[str, Any]) -> dict[str, Any]:
    """
    Build keyword arguments for Argparser based on settings.

    Args:
        settings (dict[str, Any]): Resolved configuration settings.
    """
    kwargs: dict[str, Any] = {}
    help_layout = settings.get("help_layout")
    help_colors = settings.get("help_colors")
    if help_layout is not None:
        kwargs["help_layout"] = help_layout
    if help_colors is not None:
        kwargs["help_colors"] = help_colors
    for key in (
        "flag_strategy",
        "abbreviation_gen",
        "abbreviation_max_generated_len",
        "abbreviation_scope",
        "help_option_sort",
        "print_result",
        "full_error_traceback",
        "tab_completion",
        "allow_args_from_file",
        "include_inherited_methods",
        "include_classmethods",
        "silent_interrupt",
    ):
        value = settings.get(key)
        if value is not None:
            kwargs[key] = value
    return kwargs


def _apply_layout_to_command(command: object, layout: HelpLayout) -> None:
    command.help_layout = layout
    subcommands = getattr(command, "subcommands", None)
    if isinstance(subcommands, dict):
        for subcommand in subcommands.values():
            _apply_layout_to_command(subcommand, layout)


def _apply_layout_settings(parser: InterfacyParser, settings: dict[str, Any]) -> None:
    help_layout = settings.get("help_layout")
    help_colors = settings.get("help_colors")
    if help_layout is None and help_colors is None:
        return

    layout = help_layout or parser.help_layout or InterfacyLayout()
    if help_colors is not None:
        layout.style = help_colors
    parser.help_layout = layout
    parser.help_colors = layout.style
    for command in parser.get_commands():
        _apply_layout_to_command(command, layout)


def _apply_settings_to_parser(parser: InterfacyParser, settings: dict[str, Any]) -> None:
    parser_settings = {
        "print_result": "display_result",
        "full_error_traceback": "full_error_traceback",
        "tab_completion": "enable_tab_completion",
        "allow_args_from_file": "allow_args_from_file",
        "include_inherited_methods": "include_inherited_methods",
        "include_classmethods": "include_classmethods",
        "silent_interrupt": "silent_interrupt",
        "abbreviation_max_generated_len": "abbreviation_max_generated_len",
        "abbreviation_scope": "abbreviation_scope",
        "help_option_sort": "help_option_sort",
    }
    for key, attr in parser_settings.items():
        value = settings.get(key)
        if value is not None:
            setattr(parser, attr, value)

    abbreviation_gen = settings.get("abbreviation_gen")
    if abbreviation_gen is not None:
        parser.abbreviation_gen = abbreviation_gen
    elif settings.get("abbreviation_max_generated_len") is not None and isinstance(
        parser.abbreviation_gen, DefaultAbbreviationGenerator
    ):
        parser.abbreviation_gen = DefaultAbbreviationGenerator(
            max_generated_len=parser.abbreviation_max_generated_len
        )

    _apply_layout_settings(parser, settings)
    if settings.get("help_option_sort") is not None and parser.help_layout is not None:
        parser.help_layout.help_option_sort = parser.help_option_sort


def main(argv: Sequence[str] | None = None) -> ExitCode:
    """
    Run the Interfacy CLI entrypoint.

    Args:
        argv (Sequence[str] | None): Argument list to parse. Defaults to sys.argv.
    """
    settings = resolve_entrypoint_settings()
    parser = build_parser(settings)
    args = parser.parse_args(argv)

    if args.config_paths:
        for path in _default_config_paths():
            print(path)
        return ExitCode.SUCCESS

    if not args.target:
        parser.print_help()
        return ExitCode.ERR_INVALID_ARGS

    try:
        target = resolve_target(args.target)
    except (AttributeError, FileNotFoundError, ImportError, OSError, ValueError) as exc:
        parser.error(str(exc))
        return ExitCode.ERR_INVALID_ARGS

    target_args = [arg for arg in args.ARGS if arg != "--"]

    if isinstance(target, InterfacyParser):
        _apply_settings_to_parser(target, settings)
        target.run(args=target_args)
        return ExitCode.SUCCESS

    Argparser(**build_runner_kwargs(settings)).run(target, args=target_args)
    return ExitCode.SUCCESS

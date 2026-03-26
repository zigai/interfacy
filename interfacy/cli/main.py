from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from importlib import import_module
from importlib.metadata import version
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any

from interfacy.appearance.layout import HelpLayout
from interfacy.appearance.layouts import StandardLayout
from interfacy.argparse_backend.argparser import Argparser
from interfacy.argparse_backend.argument_parser import ArgumentParser
from interfacy.cli.config import apply_config_defaults, get_default_config_paths, load_config
from interfacy.core import ExitCode, InterfacyParser


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


def load_module_from_path(path: Path) -> ModuleType:
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


def load_module(module_ref: str) -> ModuleType:
    path = Path(module_ref)
    if module_ref.endswith(".py") or path.exists():
        if not path.exists():
            raise FileNotFoundError(f"Python file not found: {path}")
        if path.is_dir():
            raise ValueError(f"Expected a Python file, got directory: {path}")
        return load_module_from_path(path)
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
    module = load_module(module_ref)
    return _resolve_symbol(module, symbol_ref)


def _is_supported_entrypoint_target(target: object) -> bool:
    from interfacy.group import CommandGroup

    if isinstance(target, (InterfacyParser, CommandGroup)):
        return False

    # Accept anything Argparser can treat as a command target
    # (functions, classes, class instances, bound methods), while
    # still excluding Interfacy-specific orchestration objects above.
    probe = Argparser(sys_exit_enabled=False, print_result=False)
    try:
        probe.add_command(target)
    except Exception:  # noqa: BLE001 - type gate for user-provided target objects
        return False
    return True


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
            "help_subcommand_sort": None,
            "print_result": None,
            "full_error_traceback": None,
            "tab_completion": None,
            "allow_args_from_file": None,
            "include_inherited_methods": None,
            "include_classmethods": None,
            "silent_interrupt": None,
        },
    )


def _resolve_help_layout(settings: dict[str, Any]) -> HelpLayout:
    help_layout = settings.get("help_layout") or StandardLayout()
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
        help=(
            "Python file or module with a function/class/instance symbol "
            "(e.g. main.py:main, pkg.cli:App, pkg.cli:service)."
        ),
    )
    parser.add_argument(
        "ARGS",
        nargs=argparse.REMAINDER,
        help="Arguments passed through to the target command.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"interfacy {version('interfacy')}",
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
        "help_subcommand_sort",
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
        for path in get_default_config_paths():
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

    if not _is_supported_entrypoint_target(target):
        parser.error(
            "Target must resolve to a function, class, or class instance. "
            "Parser instances, command groups, and other object types are not supported."
        )
        return ExitCode.ERR_INVALID_ARGS

    target_args = [arg for arg in args.ARGS if arg != "--"]

    Argparser(**build_runner_kwargs(settings)).run(target, args=target_args)
    return ExitCode.SUCCESS

from __future__ import annotations

import sys
from dataclasses import dataclass
from importlib import import_module
from importlib.util import find_spec, module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any

from interfacy.exceptions import ConfigurationError


def split_target(target: str) -> tuple[str, str]:
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

    module.__dict__["__interfacy_target_display__"] = str(path)

    return module


def _file_ref(module_ref: str) -> Path | None:
    path = Path(module_ref)
    path_like = module_ref.endswith(".py") or "/" in module_ref or "\\" in module_ref
    if not (module_ref.endswith(".py") or path.is_file() or (path_like and path.exists())):
        return None
    if not path.exists():
        raise FileNotFoundError(f"Python file not found: {path}")
    if path.is_dir():
        raise ValueError(f"Expected a Python file, got directory: {path}")

    return path


def load_module(module_ref: str) -> ModuleType:
    path = _file_ref(module_ref)
    if path is not None:
        return load_module_from_path(path)

    return import_module(module_ref)


def module_source_path(module_ref: str) -> Path:
    """
    Return the Python source file of a module or file reference without executing it.

    Finding a dotted module still imports its parent packages.

    Raises:
        ModuleNotFoundError: The module or one of its parent packages does not exist.
        ValueError: The module has no Python source file.
    """
    path = _file_ref(module_ref)
    if path is not None:
        return path

    spec = find_spec(module_ref)
    if spec is None:
        raise ModuleNotFoundError(f"No module named '{module_ref}'", name=module_ref)
    if spec.origin is None or not spec.origin.endswith(".py"):
        raise ValueError(f"Module '{module_ref}' has no Python source file")

    return Path(spec.origin)


def resolve_symbol(module: ModuleType, symbol_ref: str) -> Any:
    current: Any = module
    for part in symbol_ref.split("."):
        if not hasattr(current, part):
            display = getattr(module, "__interfacy_target_display__", module.__name__)
            raise AttributeError(f"Symbol '{symbol_ref}' not found in module '{display}'.")

        current = getattr(current, part)

    return current


def resolve_target(target: str) -> Any:
    """
    Resolve a module or file target to a Python object.

    Args:
        target (str): Target spec "module:object" or "path.py:object".
    """
    module_ref, symbol_ref = split_target(target)
    module = load_module(module_ref)

    return resolve_symbol(module, symbol_ref)


def resolve_target_with_module(target: str) -> tuple[ModuleType, Any]:
    """
    Resolve a module or file target to both the loaded module and target object.

    Args:
        target (str): Target spec "module:object" or "path.py:object".
    """
    module_ref, symbol_ref = split_target(target)
    module = load_module(module_ref)

    return module, resolve_symbol(module, symbol_ref)


@dataclass(frozen=True)
class ImportTarget:
    """A ``"module:object"`` or ``"path.py:object"`` reference that is loaded on demand."""

    module_ref: str
    symbol_ref: str

    @classmethod
    def parse(cls, target: str) -> ImportTarget:
        """
        Parse a target spec.

        Raises:
            ConfigurationError: ``target`` is not in the ``"module:object"`` form.
        """
        try:
            module_ref, symbol_ref = split_target(target)
        except ValueError as e:
            raise ConfigurationError(
                f"Command target must be 'module:object' or 'path.py:object', got '{target}'"
            ) from e

        return cls(module_ref, symbol_ref)

    def load(self) -> Any:
        """Import the module and return the referenced object."""
        return resolve_symbol(load_module(self.module_ref), self.symbol_ref)

    def __str__(self) -> str:
        return f"{self.module_ref}:{self.symbol_ref}"


__all__ = [
    "ImportTarget",
    "load_module",
    "load_module_from_path",
    "module_source_path",
    "resolve_symbol",
    "resolve_target",
    "resolve_target_with_module",
    "split_target",
]

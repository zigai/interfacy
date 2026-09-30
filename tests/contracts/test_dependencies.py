import ast
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "interfacy"

# Lowest layer first. A module may import only from its own layer or earlier layers.
LAYERS: tuple[tuple[str, ...], ...] = (
    ("common",),
    ("exceptions",),
    ("introspection",),
    ("models",),
    ("declarations",),
    ("naming",),
    ("schema",),
    ("help",),
    ("plugins",),
    ("backends", "runtime"),
    ("engine",),
    ("app",),
    ("cli",),
)
LAYER_INDEX = {name: index for index, names in enumerate(LAYERS) for name in names}
FACADE_LAYER = LAYER_INDEX["app"]

# Same-layer packages that must stay independent of each other.
ISOLATED_SIBLINGS: tuple[tuple[str, str], ...] = (("backends", "runtime"), ("runtime", "backends"))

# Function-local imports are reserved for keeping optional or heavy dependencies lazy.
ALLOWED_LOCAL_IMPORTS: frozenset[tuple[str, str]] = frozenset(
    {
        ("backends/registry.py", "interfacy.backends.argparse.adapter"),
        ("backends/registry.py", "interfacy.backends.click.adapter"),
    }
)


def imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
            continue

        if isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
            modules.update(f"{node.module}.{alias.name}" for alias in node.names)

    return modules


def package_of(module: str) -> str | None:
    parts = module.split(".")
    if parts[0] != "interfacy":
        return None
    if len(parts) == 1:
        return "app"

    return parts[1] if parts[1] in LAYER_INDEX else "app"


def module_paths() -> list[Path]:
    return sorted(
        path for path in PACKAGE_ROOT.rglob("*.py") if path.relative_to(PACKAGE_ROOT).parts
    )


def owning_package(path: Path) -> str | None:
    relative = path.relative_to(PACKAGE_ROOT)
    if relative == Path("__init__.py"):
        return None

    return relative.parts[0].removesuffix(".py")


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("import interfacy.backends.click as backend", {"interfacy.backends.click"}),
        (
            "from interfacy.backends import click as backend",
            {"interfacy.backends", "interfacy.backends.click"},
        ),
        ("from interfacy import Param", {"interfacy", "interfacy.Param"}),
        (
            "if TYPE_CHECKING:\n    from interfacy.schema.model import Command",
            {"interfacy.schema.model", "interfacy.schema.model.Command"},
        ),
    ],
)
def test_imported_modules_tracks_from_import_targets(
    tmp_path: Path,
    source: str,
    expected: set[str],
) -> None:
    path = tmp_path / "imports.py"
    path.write_text(source, encoding="utf-8")

    assert imported_modules(path) == expected


def test_every_package_has_a_layer() -> None:
    unassigned = {
        package
        for path in module_paths()
        if (package := owning_package(path)) is not None and package not in LAYER_INDEX
    }

    assert not unassigned, f"Assign these packages to a layer: {sorted(unassigned)}"


@pytest.mark.parametrize(
    "path",
    module_paths(),
    ids=lambda path: str(path.relative_to(PACKAGE_ROOT)),
)
def test_module_imports_respect_layers(path: Path) -> None:
    package = owning_package(path)
    if package is None or package not in LAYER_INDEX:
        return

    layer = LAYER_INDEX[package]
    violations: list[str] = []
    for module in sorted(imported_modules(path)):
        target = package_of(module)
        if target is None or target == package:
            continue

        if LAYER_INDEX[target] > layer:
            violations.append(f"{module} ({target} is above {package})")
        elif (package, target) in ISOLATED_SIBLINGS:
            violations.append(f"{module} ({package} must not import {target})")

    assert not violations, "Forbidden architectural imports:\n" + "\n".join(violations)


def test_package_modules_do_not_import_the_facade_root() -> None:
    violations = [
        str(path.relative_to(PACKAGE_ROOT))
        for path in module_paths()
        if (package := owning_package(path)) is not None
        and LAYER_INDEX.get(package, FACADE_LAYER) < FACADE_LAYER
        and any(module == "interfacy" for module in imported_modules(path))
    ]

    assert not violations, "Import from the defining module, not interfacy:\n" + "\n".join(
        violations
    )


def test_function_local_imports_are_limited_to_lazy_backends() -> None:
    found: set[tuple[str, str]] = set()
    for path in module_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            for inner in ast.walk(node):
                if (
                    isinstance(inner, ast.ImportFrom)
                    and inner.module is not None
                    and inner.module.startswith("interfacy")
                ):
                    found.add((path.relative_to(PACKAGE_ROOT).as_posix(), inner.module))

    unexpected = sorted(found - ALLOWED_LOCAL_IMPORTS)
    assert not unexpected, "Unexpected function-local imports:\n" + "\n".join(
        f"{path}: {module}" for path, module in unexpected
    )

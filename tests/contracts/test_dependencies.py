import ast
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "interfacy"


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
            if node.module == "interfacy" and any(
                alias.name == "Interfacy" for alias in node.names
            ):
                modules.add("interfacy.interfacy")

    return modules


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("import interfacy.click_backend as backend", {"interfacy.click_backend"}),
        (
            "from interfacy import click_backend as backend",
            {"interfacy", "interfacy.click_backend"},
        ),
        (
            "from interfacy import Interfacy as Cli",
            {"interfacy", "interfacy.Interfacy", "interfacy.interfacy"},
        ),
        (
            "if TYPE_CHECKING:\n    from interfacy import Interfacy",
            {"interfacy", "interfacy.Interfacy", "interfacy.interfacy"},
        ),
        ("from interfacy import Param", {"interfacy", "interfacy.Param"}),
        (
            "from interfacy.schema.schema import Command as SchemaCommand",
            {"interfacy.schema.schema", "interfacy.schema.schema.Command"},
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


def assert_layer_excludes(
    paths: list[Path],
    forbidden_prefixes: tuple[str, ...],
) -> None:
    violations: list[str] = []
    for path in paths:
        for module in imported_modules(path):
            if module.startswith(forbidden_prefixes):
                relative_path = path.relative_to(PACKAGE_ROOT)
                violations.append(f"{relative_path}: {module}")

    assert not violations, "Forbidden architectural imports:\n" + "\n".join(sorted(violations))


def test_schema_contracts_do_not_depend_on_presentation_or_backends() -> None:
    schema_contracts: list[Path] = [
        p for p in (PACKAGE_ROOT / "schema").glob("*.py") if p.is_file()
    ]
    assert schema_contracts, "Schema layer must contain files"
    assert_layer_excludes(
        schema_contracts,
        (
            "interfacy.argparse_backend",
            "interfacy.click_backend",
            "interfacy.cli",
            "interfacy.help",
        ),
    )


def test_runtime_does_not_depend_on_backends_or_cli() -> None:
    runtime_modules: list[Path] = list((PACKAGE_ROOT / "runtime").glob("*.py"))
    assert_layer_excludes(
        runtime_modules,
        (
            "interfacy.argparse_backend",
            "interfacy.click_backend",
            "interfacy.cli",
        ),
    )


def test_help_does_not_depend_on_backends_or_facade() -> None:
    help_modules: list[Path] = list((PACKAGE_ROOT / "help").glob("*.py"))
    assert_layer_excludes(
        help_modules,
        (
            "interfacy.argparse_backend",
            "interfacy.click_backend",
            "interfacy.interfacy",
        ),
    )


def test_backends_do_not_depend_on_public_facade() -> None:
    backend_modules: list[Path] = [
        *(PACKAGE_ROOT / "argparse_backend").glob("*.py"),
        *(PACKAGE_ROOT / "click_backend").glob("*.py"),
    ]
    assert_layer_excludes(backend_modules, ("interfacy.interfacy",))


def test_active_package_does_not_depend_on_core_or_legacy_adapters() -> None:
    active_modules: list[Path] = [path for path in PACKAGE_ROOT.rglob("*.py") if path.is_file()]
    assert_layer_excludes(
        active_modules,
        (
            "interfacy.core",
            "interfacy.argparse_backend.legacy_adapter",
            "interfacy.click_backend.legacy_adapter",
        ),
    )

import ast
from pathlib import Path

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
    return modules


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
    excluded = {
        PACKAGE_ROOT / "core.py",
        PACKAGE_ROOT / "argparse_backend" / "legacy_adapter.py",
        PACKAGE_ROOT / "click_backend" / "legacy_adapter.py",
    }
    active_modules: list[Path] = [
        path for path in PACKAGE_ROOT.rglob("*.py") if path not in excluded
    ]
    assert_layer_excludes(
        active_modules,
        (
            "interfacy.core",
            "interfacy.argparse_backend.legacy_adapter",
            "interfacy.click_backend.legacy_adapter",
        ),
    )

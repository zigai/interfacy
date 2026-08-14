from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

from interfacy import Interfacy

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_python(source: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        capture_output=True,
        check=False,
        cwd=_REPO_ROOT,
        env=env,
        text=True,
    )


def test_click_parser_does_not_publish_argparse_parser_construction_helpers() -> None:
    for name in (
        "install_tab_completion",
        "parser_from_class",
        "parser_from_function",
        "parser_from_multiple_commands",
    ):
        assert not hasattr(Interfacy, name)


def test_click_backend_defers_missing_click_import_error() -> None:
    process = _run_python(
        """
        import builtins

        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "interfacy.click_backend.adapter":
                cause = ModuleNotFoundError("No module named 'click'")
                cause.name = "click"
                exc = ImportError("adapter unavailable")
                exc.__cause__ = cause
                raise exc
            return real_import(name, globals, locals, fromlist, level)

        builtins.__import__ = fake_import

        from interfacy import Interfacy

        try:
            Interfacy(backend="click")
        except ImportError as exc:
            print(str(exc))
            print(type(exc.__cause__).__name__)
        """
    )

    assert process.returncode == 0, process.stderr
    assert "Click is required to use Interfacy with backend='click'" in process.stdout
    assert "ImportError" in process.stdout


def test_click_backend_reraises_non_click_import_error() -> None:
    process = _run_python(
        """
        import builtins

        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "interfacy.click_backend.adapter":
                cause = ModuleNotFoundError("No module named 'other_dependency'")
                cause.name = "other_dependency"
                exc = ImportError("adapter failed for another reason")
                exc.__cause__ = cause
                raise exc
            return real_import(name, globals, locals, fromlist, level)

        builtins.__import__ = fake_import

        try:
            import interfacy.click_backend  # noqa: F401
        except ImportError as exc:
            print(str(exc))
            print(exc.__cause__.name)
        """
    )

    assert process.returncode == 0, process.stderr
    assert "adapter failed for another reason" in process.stdout
    assert "other_dependency" in process.stdout

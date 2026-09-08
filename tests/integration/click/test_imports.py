from __future__ import annotations

import builtins
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

from interfacy import Interfacy
from interfacy.engine.backend import create_backend_adapter

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
        cause = ModuleNotFoundError("No module named 'other_dependency'")
        cause.name = "other_dependency"
        failure = ImportError("adapter failed for another reason")
        failure.__cause__ = cause

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "interfacy.click_backend.adapter":
                raise failure
            return real_import(name, globals, locals, fromlist, level)

        builtins.__import__ = fake_import

        from interfacy.engine.backend import create_backend_adapter

        try:
            create_backend_adapter("click")
        except ImportError as e:
            assert e is failure
            assert e.__cause__ is cause
            print(str(e))
            print(e.__cause__.name)
        else:
            raise AssertionError("Expected the original adapter import failure")
        """
    )

    assert process.returncode == 0, process.stderr
    assert "adapter failed for another reason" in process.stdout
    assert "other_dependency" in process.stdout


@pytest.mark.parametrize(
    "chain", ["direct", "cause", "context", "suppressed", "cycle", "submodule"]
)
def test_backend_factory_translates_only_visible_missing_click_failures(
    monkeypatch: pytest.MonkeyPatch, chain: str
) -> None:
    missing = ModuleNotFoundError("Click is absent", name="click")
    failure: ImportError = ImportError("Adapter initialization failed")
    if chain == "direct":
        failure = missing
    elif chain == "cause":
        failure.__cause__ = missing
    elif chain == "context":
        failure.__context__ = missing
    elif chain == "suppressed":
        failure.__context__ = missing
        failure.__suppress_context__ = True
    elif chain == "cycle":
        failure.__cause__ = failure
    else:
        failure = ModuleNotFoundError("Click submodule is absent", name="click.missing")

    original_import = builtins.__import__

    def import_adapter(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "interfacy.click_backend.adapter":
            raise failure

        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_adapter)

    with pytest.raises(ImportError) as e:
        create_backend_adapter("click")

    if chain in {"direct", "cause", "context"}:
        assert e.value is not failure
        assert e.value.__cause__ is failure
        assert "Click is required" in str(e.value)
    else:
        assert e.value is failure

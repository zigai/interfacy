from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

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


def test_click_backend_defers_missing_click_import_error() -> None:
    process = _run_python(
        """
        import sys

        sys.modules["click"] = None

        from interfacy import Interfacy

        Interfacy(backend="argparse")

        try:
            Interfacy(backend="click")
        except ImportError as exc:
            print(str(exc))
        else:
            raise AssertionError("Expected missing Click to be reported")
        """
    )

    assert process.returncode == 0, process.stderr
    assert "Click is required to use Interfacy with backend='click'" in process.stdout

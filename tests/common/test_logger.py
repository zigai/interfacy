from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_python(
    source: str,
    *,
    env_overrides: dict[str, str | None] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key, value in (env_overrides or {}).items():
        if value is None:
            env.pop(key, None)
            continue

        env[key] = value

    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        capture_output=True,
        check=False,
        cwd=_REPO_ROOT,
        env=env,
        text=True,
    )


def test_get_logger_uses_null_handler_without_interfacy_log_env() -> None:
    process = _run_python(
        """
        import json
        from interfacy.logger import get_logger

        logger = get_logger("tests.logger")
        print(json.dumps([type(handler).__name__ for handler in logger.handlers]))
        logger.info("should stay quiet")
        """
    )

    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == ["NullHandler"]
    assert process.stderr == ""


def test_get_logger_emits_to_stderr_when_interfacy_log_is_set() -> None:
    process = _run_python(
        """
        from interfacy.logger import get_logger

        logger = get_logger("tests.logger")
        logger.info("enabled message")
        """,
        env_overrides={"INTERFACY_LOG": "INFO"},
    )

    assert process.returncode == 0, process.stderr
    assert "enabled message" in process.stderr

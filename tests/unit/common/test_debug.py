from __future__ import annotations

import logging
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from interfacy.common.console import log_exception
from interfacy.common.debug import ClickableFormatter

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
        from interfacy.common.debug import get_logger

        logger = get_logger("tests.logger")
        logger.info("should stay quiet")
        """,
        env_overrides={"INTERFACY_LOG": None},
    )

    assert process.returncode == 0, process.stderr
    assert process.stderr == ""


def test_get_logger_emits_to_stderr_when_interfacy_log_is_set() -> None:
    process = _run_python(
        """
        from interfacy.common.debug import get_logger

        logger = get_logger("tests.logger")
        logger.info("enabled message")
        """,
        env_overrides={"INTERFACY_LOG": "INFO"},
    )

    assert process.returncode == 0, process.stderr
    assert "enabled message" in process.stderr


def test_interfacy_log_does_not_emit_command_values() -> None:
    process = _run_python(
        """
        from interfacy import Interfacy

        def login(api_key: str) -> str:
            return api_key

        parser = Interfacy(print_result=False)
        result = parser.invoke(login, args=["SECRET_TOKEN"])
        assert result == "SECRET_TOKEN"
        """,
        env_overrides={"INTERFACY_LOG": "INFO"},
    )

    assert process.returncode == 0, process.stderr
    assert "Calling function 'login'" in process.stderr
    assert "SECRET_TOKEN" not in process.stderr


def test_get_logger_treats_interfacy_log_one_as_info() -> None:
    process = _run_python(
        """
        from interfacy.common.debug import get_logger

        logger = get_logger("tests.logger")
        logger.debug("debug stays hidden")
        logger.info("one means info")
        """,
        env_overrides={"INTERFACY_LOG": "1"},
    )

    assert process.returncode == 0, process.stderr
    assert "one means info" in process.stderr
    assert "debug stays hidden" not in process.stderr


def test_get_logger_accepts_numeric_interfacy_log_level() -> None:
    process = _run_python(
        """
        from interfacy.common.debug import get_logger

        logger = get_logger("tests.logger")
        logger.debug("debug enabled")
        """,
        env_overrides={"INTERFACY_LOG": str(logging.DEBUG)},
    )

    assert process.returncode == 0, process.stderr
    assert "debug enabled" in process.stderr


def test_get_logger_ignores_blank_interfacy_log_env() -> None:
    process = _run_python(
        """
        from interfacy.common.debug import get_logger

        logger = get_logger("tests.logger")
        logger.error("still quiet")
        """,
        env_overrides={"INTERFACY_LOG": "   "},
    )

    assert process.returncode == 0, process.stderr
    assert process.stderr == ""


def test_clickable_formatter_populates_record_fields() -> None:
    record = logging.LogRecord(
        name="interfacy.schema.builder",
        level=logging.ERROR,
        pathname=__file__,
        lineno=123,
        msg="boom",
        args=(),
        exc_info=None,
    )
    formatter = ClickableFormatter(
        "%(colored_levelname)s|%(short_name)s|%(name_location)s|%(message)s"
    )

    formatted = formatter.format(record)

    assert "ERROR" in formatted
    assert "|schema|" in formatted
    assert "test_debug.py:123" in formatted
    assert "boom" in formatted


def test_log_exception_formats_the_supplied_exception_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    try:
        raise ValueError("boom")  # noqa: TRY301 - capture this exact traceback for the API test
    except ValueError as e:
        error = e

    log_exception("test", error, full_traceback=True)

    stderr = capsys.readouterr().err
    assert "test_log_exception_formats_the_supplied_exception_traceback" in stderr
    assert "ValueError: boom" in stderr
    assert "NoneType: None" not in stderr

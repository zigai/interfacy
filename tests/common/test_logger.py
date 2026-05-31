from __future__ import annotations

import json
import logging
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


def test_get_logger_treats_interfacy_log_one_as_info() -> None:
    process = _run_python(
        """
        import json
        import logging
        from interfacy.logger import get_logger

        logger = get_logger("tests.logger")
        handler = logger.handlers[0]
        print(json.dumps({"logger": logger.level, "handler": handler.level}))
        logger.info("one means info")
        """,
        env_overrides={"INTERFACY_LOG": "1"},
    )

    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == {
        "logger": logging.INFO,
        "handler": logging.INFO,
    }
    assert "one means info" in process.stderr


def test_get_logger_accepts_numeric_interfacy_log_level() -> None:
    process = _run_python(
        """
        import json
        import logging
        from interfacy.logger import get_logger

        logger = get_logger("tests.logger")
        handler = logger.handlers[0]
        print(json.dumps({"logger": logger.level, "handler": handler.level}))
        logger.debug("debug enabled")
        """,
        env_overrides={"INTERFACY_LOG": str(logging.DEBUG)},
    )

    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == {
        "logger": logging.DEBUG,
        "handler": logging.DEBUG,
    }
    assert "debug enabled" in process.stderr


def test_get_logger_ignores_blank_interfacy_log_env() -> None:
    process = _run_python(
        """
        import json
        from interfacy.logger import get_logger

        logger = get_logger("tests.logger")
        print(json.dumps([type(handler).__name__ for handler in logger.handlers]))
        logger.error("still quiet")
        """,
        env_overrides={"INTERFACY_LOG": "   "},
    )

    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == ["NullHandler"]
    assert process.stderr == ""


def test_get_logger_maps_main_to_interfacy_root_logger() -> None:
    process = _run_python(
        """
        from interfacy.logger import get_logger

        print(get_logger("__main__").name)
        """,
    )

    assert process.returncode == 0, process.stderr
    assert process.stdout.strip() == "interfacy"


def test_clickable_formatter_shortens_interfacy_logger_names() -> None:
    process = _run_python(
        """
        from interfacy.logger import get_logger

        get_logger("interfacy.schema.builder").warning("schema warning")
        get_logger("external.module").warning("external warning")
        """,
        env_overrides={"INTERFACY_LOG": "WARNING"},
    )

    assert process.returncode == 0, process.stderr
    assert "schema." in process.stderr
    assert "external." in process.stderr
    assert "schema warning" in process.stderr
    assert "external warning" in process.stderr


def test_get_level_parses_supported_environment_values(monkeypatch) -> None:
    from interfacy import logger as logger_module

    monkeypatch.setenv("INTERFACY_LOG", "1")
    assert logger_module._get_level() == logging.INFO

    monkeypatch.setenv("INTERFACY_LOG", "10")
    assert logger_module._get_level() == logging.DEBUG

    monkeypatch.setenv("INTERFACY_LOG", "warning")
    assert logger_module._get_level() == logging.WARNING

    monkeypatch.setenv("INTERFACY_LOG", "not-a-level")
    assert logger_module._get_level() == logging.INFO


def test_get_level_returns_none_for_missing_or_blank_environment(monkeypatch) -> None:
    from interfacy import logger as logger_module

    monkeypatch.delenv("INTERFACY_LOG", raising=False)
    assert logger_module._get_level() is None

    monkeypatch.setenv("INTERFACY_LOG", " ")
    assert logger_module._get_level() is None


def test_setup_logger_uses_stream_handler_when_global_logging_enabled(monkeypatch) -> None:
    from interfacy import logger as logger_module

    monkeypatch.delenv("INTERFACY_LOG", raising=False)
    monkeypatch.setattr(logger_module, "ENABLED", True)
    logger = logging.getLogger("interfacy.tests.direct-enabled")
    logger.handlers.clear()

    logger_module._setup_logger(logger)

    assert logger.level == logging.INFO
    assert [type(handler).__name__ for handler in logger.handlers] == ["StreamHandler"]
    assert logger.propagate is False

    logger.handlers.clear()


def test_clickable_formatter_populates_record_fields() -> None:
    from interfacy.logger import ClickableFormatter

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
    assert "test_logger.py:123" in formatted
    assert "boom" in formatted


def test_clickable_formatter_keeps_external_logger_name() -> None:
    from interfacy.logger import ClickableFormatter

    record = logging.LogRecord(
        name="external.module",
        level=logging.INFO,
        pathname=__file__,
        lineno=321,
        msg="outside",
        args=(),
        exc_info=None,
    )

    ClickableFormatter("%(short_name)s").format(record)

    assert record.short_name == "external.module"

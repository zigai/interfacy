import logging
import os
from logging import _nameToLevel

from stdl.st import colored, terminal_link

_LOGGER_PREFIX = "interfacy"
ENABLED = True


LEVEL_COLORS = {
    "DEBUG": "cyan",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "magenta",
}


def _get_level() -> int:
    level_name = os.getenv("INTERFACY_LOG") or "NOTSET"
    level_name = "INFO" if level_name == 1 else level_name
    return _nameToLevel.get(level_name, logging.NOTSET)


def get_logger(name: str) -> logging.Logger:
    if not name.startswith(_LOGGER_PREFIX):
        logger_name = f"{_LOGGER_PREFIX}.{name}" if name != "__main__" else _LOGGER_PREFIX
    else:
        logger_name = name
    logger = logging.getLogger(logger_name)
    if not logger.handlers:
        _setup_logger(logger)
    return logger


class _ClickableFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        filename = os.path.basename(record.pathname)
        label = f"{filename}:{record.lineno}"
        record.clickable_path = terminal_link(f"{record.pathname}:{record.lineno}", label)
        colored_level = colored(record.levelname, color=LEVEL_COLORS.get(record.levelname, "white"))

        max_level_width = 8
        max_total_width = 40

        padding = max_level_width - len(record.levelname)
        record.colored_levelname = colored_level + (" " * padding)

        if record.name.startswith(_LOGGER_PREFIX):
            parts = record.name.split(".")
            if len(parts) > 1:
                record.short_name = parts[1]
            else:
                record.short_name = _LOGGER_PREFIX
        else:
            record.short_name = record.name

        combined = f"{record.short_name}.{label}"  # type:ignore
        visible_length = len(combined)
        combined_with_link = f"{record.short_name}.{record.clickable_path}"  # type:ignore
        padding_needed = max(0, max_total_width - visible_length)
        record.name_location = combined_with_link + (" " * padding_needed)

        return super().format(record)


def _setup_logger(logger: logging.Logger) -> None:
    level = _get_level()
    logger.setLevel(level)

    if ENABLED:
        handler: logging.Handler = logging.StreamHandler()
        handler.setLevel(level)
        formatter = _ClickableFormatter(
            fmt="%(colored_levelname)s | %(name_location)s | %(message)s",
        )
        handler.setFormatter(formatter)
    else:
        handler = logging.NullHandler()

    logger.addHandler(handler)
    logger.propagate = False


__all__ = ["get_logger"]

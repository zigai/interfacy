import logging
import os

from interfacy.common.log_formatter import LOGGER_PREFIX, ClickableFormatter

ENABLED = False


def _get_level() -> int | None:
    level_name = os.getenv("INTERFACY_LOG")
    if level_name is None:
        return None

    normalized = level_name.strip()
    if not normalized:
        return None

    normalized = "INFO" if normalized == "1" else normalized
    if normalized.isdigit():
        return int(normalized)

    return logging.getLevelNamesMapping().get(normalized.upper(), logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """
    Return a configured logger in the interfacy namespace.

    Args:
        name (str): Logger name or module name.
    """
    if not name.startswith(LOGGER_PREFIX):
        logger_name = f"{LOGGER_PREFIX}.{name}" if name != "__main__" else LOGGER_PREFIX
    else:
        logger_name = name
    logger = logging.getLogger(logger_name)
    if not logger.handlers:
        _setup_logger(logger)

    return logger


def _setup_logger(logger: logging.Logger) -> None:
    level = _get_level()
    logger.disabled = False

    if ENABLED or level is not None:
        effective_level = logging.INFO if level is None else level
        logger.setLevel(effective_level)
        handler: logging.Handler = logging.StreamHandler()
        handler.setLevel(effective_level)
        formatter = ClickableFormatter(
            fmt="%(colored_levelname)s | %(name_location)s | %(message)s",
        )
        handler.setFormatter(formatter)
    else:
        logger.setLevel(logging.NOTSET)

        handler = logging.NullHandler()

    logger.addHandler(handler)
    logger.propagate = False


__all__ = ["get_logger"]

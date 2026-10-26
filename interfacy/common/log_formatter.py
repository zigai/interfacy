import logging
from pathlib import Path

from stdl.st import colored, terminal_link

LOGGER_PREFIX = "interfacy"

LEVEL_COLORS = {
    "DEBUG": "cyan",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "magenta",
}


class ClickableFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record with a clickable path and padded name column.

        Args:
            record (logging.LogRecord): Log record to format.
        """
        filename = Path(record.pathname).name
        label = f"{filename}:{record.lineno}"
        record.clickable_path = terminal_link(f"{record.pathname}:{record.lineno}", label)
        colored_level = colored(record.levelname, color=LEVEL_COLORS.get(record.levelname, "white"))

        max_level_width = 8
        max_total_width = 40

        padding = max_level_width - len(record.levelname)
        record.colored_levelname = colored_level + (" " * padding)

        if record.name.startswith(LOGGER_PREFIX):
            parts = record.name.split(".")
            if len(parts) > 1:
                record.short_name = parts[1]
            else:
                record.short_name = LOGGER_PREFIX
        else:
            record.short_name = record.name

        combined = f"{record.short_name}.{label}"  # type: ignore[attr-defined]
        visible_length = len(combined)
        combined_with_link = f"{record.short_name}.{record.clickable_path}"  # type: ignore[attr-defined]
        padding_needed = max(0, max_total_width - visible_length)
        record.name_location = combined_with_link + (" " * padding_needed)

        return super().format(record)


__all__ = ["LOGGER_PREFIX", "ClickableFormatter"]

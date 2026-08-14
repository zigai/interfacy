import os
import re


def get_terminal_width(default: int = 80) -> int:
    """
    Return terminal width in columns with a safe fallback.

    Args:
        default (int): Width to return when terminal size cannot be detected.
    """
    try:
        return os.get_terminal_size().columns
    except (OSError, AttributeError):
        return default


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from a string."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)

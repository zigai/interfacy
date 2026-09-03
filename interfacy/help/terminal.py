import re
import shutil

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def get_terminal_width(default: int = 80) -> int:
    """
    Return terminal width in columns with a safe fallback.

    Args:
        default (int): Width to return when terminal size cannot be detected.
    """
    return shutil.get_terminal_size(fallback=(default, 24)).columns


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from a string."""
    return _ANSI_RE.sub("", text)

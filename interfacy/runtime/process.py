import sys
from pathlib import PurePosixPath

from setproctitle import setproctitle

_DEFAULT_PROCESS_TITLE = "interfacy"


def derive_process_title(argv0: str | None = None) -> str:
    """
    Derive a user-facing process title from argv[0].

    Args:
        argv0 (str | None): Executable path/name override. Defaults to sys.argv[0].
    """
    candidate = argv0
    if candidate is None:
        candidate = sys.argv[0] if sys.argv else ""
    candidate = candidate.strip()
    if not candidate:
        return _DEFAULT_PROCESS_TITLE

    normalized = candidate.replace("\\", "/")
    title = PurePosixPath(normalized).name.removesuffix(".exe")
    if not title:
        return _DEFAULT_PROCESS_TITLE

    return title


def set_process_title(title: str) -> bool:
    """
    Set process title using best available mechanism.

    Args:
        title (str): Target process title.
    """
    normalized = title.strip()
    if not normalized:
        return False

    try:
        setproctitle(normalized)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        return False

    return True


def set_process_title_from_argv(argv0: str | None = None) -> bool:
    """
    Derive and apply process title from argv[0].

    Args:
        argv0 (str | None): Executable path/name override.
    """
    return set_process_title(derive_process_title(argv0))

from __future__ import annotations

from interfacy.exceptions import UsageError


class ArgparseParseError(UsageError):
    """Internal recoverable argparse parse error with backend-neutral failure facts."""


__all__ = ["ArgparseParseError"]

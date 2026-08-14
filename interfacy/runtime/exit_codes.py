from enum import IntEnum


class ExitCode(IntEnum):
    """Stable process exit codes emitted by :meth:`Interfacy.run`."""

    SUCCESS = 0
    COMMAND_FAILED = 1
    USAGE = 2
    INTERNAL = 70
    CONFIGURATION = 78
    INTERRUPTED = 130


__all__ = ["ExitCode"]

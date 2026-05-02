from __future__ import annotations

from interfacy.executable_flag import ExecutableFlag
from interfacy.group import CommandGroup
from interfacy.interfacy import Interfacy


def __dir__() -> list[str]:
    return sorted(__all__)


__all__ = ["CommandGroup", "ExecutableFlag", "Interfacy"]

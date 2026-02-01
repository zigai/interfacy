from __future__ import annotations

from typing import TYPE_CHECKING

from interfacy.argparse_backend.argparser import Argparser
from interfacy.group import CommandGroup

if TYPE_CHECKING:  # pragma: no cover
    from interfacy.click_backend import ClickParser as ClickParser

__all__ = ["Argparser", "CommandGroup", "ClickParser"]


def __getattr__(name: str) -> type[ClickParser]:
    if name != "ClickParser":
        raise AttributeError(f"module '{__name__}' has no attribute {name!r}")
    try:
        from interfacy.click_backend import ClickParser as _ClickParser
    except ImportError as exc:  # pragma: no cover - optional dependency guard
        raise ImportError(
            "Click is required to use ClickParser. Install it with "
            "\"pip install 'interfacy[click]'\" or \"uv add 'interfacy[click]'\"."
        ) from exc
    return _ClickParser


def __dir__() -> list[str]:
    return sorted(__all__)

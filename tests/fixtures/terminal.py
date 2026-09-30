"""Terminal-size control for help rendering tests."""

import os
import shutil

import pytest


def freeze_terminal(monkeypatch: pytest.MonkeyPatch, width: int) -> None:
    """Make every terminal-size lookup report ``width`` columns."""
    size = os.terminal_size((width, 24))
    monkeypatch.setattr(os, "get_terminal_size", lambda *args, **kwargs: size)
    monkeypatch.setattr(shutil, "get_terminal_size", lambda *args, **kwargs: size)
    monkeypatch.setenv("COLUMNS", str(width))

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any


def freeze(value: Any) -> Any:
    """Return a read-only copy of nested mappings, sequences, and sets."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(freeze(item) for item in value)
    return value


__all__ = ["freeze"]

from __future__ import annotations

from collections.abc import Iterable

from objinspect import Class, Function, Method


class Command:
    """Container for callable metadata tracked by Interfacy."""

    __slots__ = ("obj", "name", "description", "pipe_target", "aliases")

    def __init__(
        self,
        obj: Function | Method | Class,
        name: str | None = None,
        description: str | None = None,
        pipe_target: dict[str, str] | str | None = None,
        aliases: Iterable[str] | str | None = None,
    ) -> None:
        self.obj = obj
        self.name = name
        self.description = description
        self.pipe_target = pipe_target
        self.aliases = self._normalize_aliases(aliases)

    @staticmethod
    def _normalize_aliases(aliases: Iterable[str] | str | None) -> tuple[str, ...]:
        if aliases is None:
            return ()
        if isinstance(aliases, str):
            return (aliases,)
        if isinstance(aliases, tuple):
            return aliases
        return tuple(aliases)

    def __repr__(self) -> str:
        return (
            f"Command(obj={self.obj!r}, name={self.name!r}, description={self.description!r}, "
            f"pipe_target={self.pipe_target!r}, aliases={self.aliases!r})"
        )

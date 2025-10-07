from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from objinspect import Class, Function, Method

from interfacy.pipe import PipeTargets, build_pipe_targets_config


class Command:
    """Container for callable metadata tracked by Interfacy."""

    __slots__ = (
        "obj",
        "name",
        "description",
        "pipe_targets",
        "aliases",
        "_pipe_overrides",
    )

    def __init__(
        self,
        obj: Function | Method | Class,
        name: str | None = None,
        description: str | None = None,
        aliases: Iterable[str] | str | None = None,
        pipe_targets: PipeTargets | dict[str, Any] | Sequence[str] | str | None = None,
    ) -> None:
        self.obj = obj
        self.name = name
        self.description = description
        self.pipe_targets: PipeTargets | None = (
            build_pipe_targets_config(pipe_targets) if pipe_targets is not None else None
        )
        self._pipe_overrides: dict[str, PipeTargets] = {}
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
            f"pipe_targets={self.pipe_targets!r}, aliases={self.aliases!r}, "
            f"overrides={self._pipe_overrides!r})"
        )

    def pipe_to(self, targets, *, subcommand: str | None = None, **normalization_kwargs) -> Command:
        """Register pipe targets for this command or one of its subcommands."""
        if "precedence" in normalization_kwargs and "priority" not in normalization_kwargs:
            normalization_kwargs["priority"] = normalization_kwargs.pop("precedence")
        config = build_pipe_targets_config(targets, **normalization_kwargs)
        if subcommand is None:
            self.pipe_targets = config
        else:
            self._pipe_overrides[subcommand] = config
        return self

    def get_pipe_targets(self, *, subcommand: str | None = None) -> PipeTargets | None:
        if subcommand is not None:
            if subcommand in self._pipe_overrides:
                return self._pipe_overrides[subcommand]
        if self.pipe_targets is not None:
            return self.pipe_targets
        return None

    def get_all_pipe_overrides(self) -> dict[str, PipeTargets]:
        return dict(self._pipe_overrides)

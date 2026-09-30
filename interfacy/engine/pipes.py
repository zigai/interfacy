from __future__ import annotations

import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from stdl.fs import read_piped

from interfacy.declarations.pipes import PipeTargets, build_pipe_targets_config
from interfacy.naming import NameMapping
from interfacy.schema.model import Command

_PIPE_UNSET = object()


@dataclass(frozen=True, slots=True)
class PipeStateSnapshot:
    default_targets: PipeTargets | None
    overrides: dict[tuple[str | None, str | None], PipeTargets]
    input_buffer: Any


class PipeState:
    def __init__(
        self,
        command_names: NameMapping,
        default_targets: PipeTargets | None = None,
    ) -> None:
        self._command_names = command_names
        self.default_targets = default_targets
        self._overrides: dict[tuple[str | None, str | None], PipeTargets] = {}
        self._input_buffer: Any = _PIPE_UNSET

    def configure(
        self,
        targets: PipeTargets | dict[str, Any] | Sequence[str] | str,
        *,
        command: str | None = None,
        subcommand: str | None = None,
        **normalization_kwargs: Any,
    ) -> PipeTargets:
        if "precedence" in normalization_kwargs and "priority" not in normalization_kwargs:
            normalization_kwargs["priority"] = normalization_kwargs.pop("precedence")
        config = build_pipe_targets_config(targets, **normalization_kwargs)
        if command is None:
            self.default_targets = config
            return config

        self._overrides[(command, subcommand)] = config

        return config

    def resolve(
        self,
        command: Command,
        *,
        subcommand: str | None = None,
    ) -> PipeTargets | None:
        raw_names = (
            command.canonical_name,
            command.cli_name,
            *(command.aliases or ()),
            command.obj.name if command.obj is not None else None,
        )
        names = list(dict.fromkeys(name for name in raw_names if name))
        for key in self._override_keys(names, subcommand):
            target = self._overrides.get(key)
            if target is not None:
                return target

        if subcommand in (None, "__init__") and command.pipe_targets is not None:
            return command.pipe_targets

        return self.default_targets

    def resolve_by_names(
        self,
        *,
        canonical_name: str,
        obj_name: str | None,
        aliases: tuple[str, ...] = (),
        subcommand: str | None = None,
        include_default: bool = True,
    ) -> PipeTargets | None:
        names: list[str] = [canonical_name]
        for name in (obj_name, *aliases):
            if name and name not in names:
                names.append(name)

        for key in self._override_keys(names, subcommand):
            target = self._overrides.get(key)
            if target is not None:
                return target

        return self.default_targets if include_default else None

    def read_input(self) -> str | None:
        if self._input_buffer is _PIPE_UNSET:
            self._input_buffer = None if sys.stdin.isatty() else read_piped()

        return self._input_buffer if isinstance(self._input_buffer, str) else None

    def reset_input(self) -> None:
        self._input_buffer = _PIPE_UNSET

    def snapshot(self) -> PipeStateSnapshot:
        return PipeStateSnapshot(
            default_targets=self.default_targets,
            overrides=dict(self._overrides),
            input_buffer=self._input_buffer,
        )

    def restore(self, snapshot: PipeStateSnapshot) -> None:
        self.default_targets = snapshot.default_targets
        self._overrides = dict(snapshot.overrides)
        self._input_buffer = snapshot.input_buffer

    def _override_keys(
        self,
        names: list[str],
        subcommand: str | None,
    ) -> Iterable[tuple[str | None, str | None]]:
        subcommands: list[str | None] = [subcommand]
        if subcommand is not None:
            reverse = self._command_names.reverse(subcommand)
            if reverse != subcommand:
                subcommands.append(reverse)

        for name in names:
            for candidate in subcommands:
                yield name, candidate

        yield None, subcommand

        if len(subcommands) > 1:
            yield None, subcommands[1]

        yield None, None


__all__ = ["PipeState", "PipeStateSnapshot"]

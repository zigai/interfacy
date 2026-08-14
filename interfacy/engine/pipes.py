from __future__ import annotations

import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from stdl.fs import read_piped

from interfacy.naming import NameMapping
from interfacy.pipe import PipeTargets, build_pipe_targets_config
from interfacy.schema.schema import Command, ParserSchema

_PIPE_UNSET = object()


@dataclass(frozen=True, slots=True)
class PipeStateSnapshot:
    default_targets: PipeTargets | None
    overrides: dict[tuple[str | None, str | None], PipeTargets]
    input_buffer: object
    cli_namespace: dict[str, Any] | None


class PipeState:
    def __init__(
        self,
        command_names: NameMapping,
        default_targets: PipeTargets | None = None,
    ) -> None:
        self._command_names = command_names
        self.default_targets = default_targets
        self._overrides: dict[tuple[str | None, str | None], PipeTargets] = {}
        self._input_buffer: object = _PIPE_UNSET
        self._cli_namespace: dict[str, Any] | None = None

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
        names: list[str] = []
        for name in (command.canonical_name, command.cli_name, *(command.aliases or ())):
            if name and name not in names:
                names.append(name)
        if command.obj is not None and command.obj.name not in names:
            names.append(command.obj.name)
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

    def record_cli_namespace(self, namespace: dict[str, Any] | None) -> None:
        self._cli_namespace = namespace

    def cli_supplied_parameters(
        self,
        command: Command,
        *,
        subcommand: str | None = None,
    ) -> set[str] | None:
        namespace = self._cli_namespace
        if namespace is None:
            return None
        bucket = self._command_bucket(namespace, command)
        if subcommand not in (None, "__init__"):
            bucket = self._subcommand_bucket(bucket, command, subcommand)
        return set(bucket) if isinstance(bucket, dict) else set()

    def schema_uses_pipes(self, schema: ParserSchema) -> bool:
        if schema.pipe_targets is not None or self.default_targets is not None or self._overrides:
            return True
        return any(self._command_uses_pipes(command) for command in schema.commands.values())

    def snapshot(self) -> PipeStateSnapshot:
        namespace = None if self._cli_namespace is None else dict(self._cli_namespace)
        return PipeStateSnapshot(
            default_targets=self.default_targets,
            overrides=dict(self._overrides),
            input_buffer=self._input_buffer,
            cli_namespace=namespace,
        )

    def restore(self, snapshot: PipeStateSnapshot) -> None:
        self.default_targets = snapshot.default_targets
        self._overrides = dict(snapshot.overrides)
        self._input_buffer = snapshot.input_buffer
        self._cli_namespace = (
            None if snapshot.cli_namespace is None else dict(snapshot.cli_namespace)
        )

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

    @staticmethod
    def _command_uses_pipes(command: Command) -> bool:
        if command.pipe_targets is not None:
            return True
        if any(argument.accepts_stdin for argument in (*command.initializer, *command.parameters)):
            return True
        return bool(
            command.subcommands
            and any(PipeState._command_uses_pipes(child) for child in command.subcommands.values())
        )

    @staticmethod
    def _command_names_for(command: Command) -> tuple[str, ...]:
        names: list[str] = []
        for name in (command.canonical_name, command.cli_name, *(command.aliases or ())):
            if name and name not in names:
                names.append(name)
        if command.obj is not None and command.obj.name not in names:
            names.append(command.obj.name)
        return tuple(names)

    def _command_bucket(self, namespace: dict[str, Any], command: Command) -> dict[str, Any]:
        for name in self._command_names_for(command):
            value = namespace.get(name)
            if isinstance(value, dict):
                return value
        return namespace

    def _subcommand_bucket(
        self,
        bucket: dict[str, Any],
        command: Command,
        subcommand: str,
    ) -> dict[str, Any]:
        candidates: list[str] = [subcommand]
        for name in (
            self._command_names.translate(subcommand),
            self._command_names.reverse(subcommand),
        ):
            if name not in candidates:
                candidates.append(name)
        if command.subcommands:
            for child in command.subcommands.values():
                names = self._command_names_for(child)
                if any(name in candidates for name in names):
                    candidates.extend(name for name in names if name not in candidates)
        nested = bucket.get("_subcommands")
        containers = (bucket, nested) if isinstance(nested, dict) else (bucket,)
        for container in containers:
            for name in candidates:
                value = container.get(name)
                if isinstance(value, dict):
                    return value
        return {}


__all__ = ["PipeState", "PipeStateSnapshot"]

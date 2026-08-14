from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal

from objinspect.typing import get_literal_choices

from interfacy.exceptions import ConfigurationError

PipePriority = Literal["cli", "pipe"]
DELIMITER_UNSET = ...


@dataclass(frozen=True)
class PipeTargets:
    """
    Configuration for routing stdin content to parameters.

    Attributes:
        targets: Ordered parameter names that receive piped chunks.
            The order defines how chunks map to parameters.
        delimiter: Chunk delimiter. If ``None``, chunking uses line breaks. If
            more than one target is set and the delimiter is not explicitly
            provided, a newline is assumed by default.
        priority: Conflict resolution policy.
            - ``"cli"`` keeps explicit CLI arguments and only fills missing ones from the pipe.
            - ``"pipe"`` overwrites CLI values with piped data.
        allow_partial: If True, fewer chunks than targets are allowed.
            Missing chunks become ``None`` and are ignored unless the parameter is required.
    """

    targets: tuple[str, ...]
    delimiter: str | None = None
    priority: PipePriority = "cli"
    allow_partial: bool = False

    def targeted_parameters(self) -> set[str]:
        """Return the set of configured target parameter names."""
        return set(self.targets)


TargetsInput = PipeTargets | str | Sequence[str] | dict[str, Any]


def parse_priority(value: str | None) -> PipePriority:
    """Parse a user-supplied priority value. Defaults to 'cli' if value is None."""
    if value is None:
        return "cli"
    if value in ("cli", "pipe"):
        return value

    choices = tuple(str(choice) for choice in get_literal_choices(PipePriority))

    raise ConfigurationError(f"Invalid pipe priority '{value}'. Valid values: {','.join(choices)}")


def targets_to_list(value: str | Sequence[Any]) -> list[str]:
    """
    Normalize pipe target input into a list of unique names.

    Args:
        value (str | Sequence[Any]): String or sequence to normalize.

    Raises:
        ConfigurationError: If the value cannot be interpreted as target names or contains invalid/duplicate entries.
    """
    if isinstance(value, str):
        names = [value]
    elif isinstance(value, Sequence):
        names = list(value)
    else:
        raise ConfigurationError("Pipe targets must be a string or a sequence of strings")

    result: list[str] = []
    seen: set[str] = set()
    for name in names:
        if not isinstance(name, str) or not name:
            raise ConfigurationError("Pipe target names must be non-empty strings")
        if name in seen:
            raise ConfigurationError(f"Duplicate pipe target for parameter '{name}'")

        result.append(name)
        seen.add(name)

    if not result:
        raise ConfigurationError("At least one pipe target is required")

    return result


def _normalize_allow_partial(value: bool | None) -> bool | None:
    if value is not None and not isinstance(value, bool):
        raise ConfigurationError("Pipe allow_partial must be a bool")

    return value


def _replace_pipe_targets(
    config: PipeTargets,
    *,
    delimiter: str | Any | None,
    allow_partial: bool | None,
    priority: str | PipePriority | None,
) -> PipeTargets:
    if config.delimiter is not None and not isinstance(config.delimiter, str):
        raise ConfigurationError("Pipe delimiter must be a string or None")

    updated = replace(
        config,
        targets=tuple(targets_to_list(config.targets)),
        priority=parse_priority(config.priority),
        allow_partial=_normalize_allow_partial(config.allow_partial) or False,
    )
    if delimiter is not DELIMITER_UNSET:
        if delimiter is not None and not isinstance(delimiter, str):
            raise ConfigurationError("Pipe delimiter must be a string or None")

        updated = replace(updated, delimiter=delimiter)

    normalized_allow_partial = _normalize_allow_partial(allow_partial)
    if normalized_allow_partial is not None:
        updated = replace(updated, allow_partial=normalized_allow_partial)

    if priority is not None:
        updated = replace(updated, priority=parse_priority(priority))

    return updated


def _resolve_pipe_target_inputs(
    targets: TargetsInput,
    *,
    delimiter: str | Any | None,
    allow_partial: bool | None,
    priority: str | PipePriority | None,
) -> tuple[Any, bool, str | None, bool | None, str | PipePriority | None]:
    names_value: Any = targets
    delimiter_explicit = delimiter is not DELIMITER_UNSET

    if delimiter is DELIMITER_UNSET:
        final_delimiter: str | None = None
    elif delimiter is None or isinstance(delimiter, str):
        final_delimiter = delimiter
    else:
        raise ConfigurationError("Pipe delimiter must be a string or None")
    resolved_allow_partial = _normalize_allow_partial(allow_partial)
    resolved_priority = priority

    if isinstance(targets, dict):
        names_value = targets.get("parameters") or targets.get("bindings")
        if names_value is None:
            raise ConfigurationError(
                "Pipe target dict must include 'parameters' or 'bindings' entries"
            )

        if "delimiter" in targets and delimiter is DELIMITER_UNSET:
            delimiter_explicit = True
            delimiter_value = targets.get("delimiter")
            if delimiter_value is not None and not isinstance(delimiter_value, str):
                raise ConfigurationError("Pipe delimiter must be a string or None")

            final_delimiter = delimiter_value

        if resolved_allow_partial is None and "allow_partial" in targets:
            resolved_allow_partial = _normalize_allow_partial(targets["allow_partial"])

        if resolved_priority is None and "priority" in targets:
            resolved_priority = targets["priority"]

    return (
        names_value,
        delimiter_explicit,
        final_delimiter,
        resolved_allow_partial,
        resolved_priority,
    )


def build_pipe_targets_config(
    targets: TargetsInput,
    *,
    delimiter: str | Any | None = DELIMITER_UNSET,
    allow_partial: bool | None = None,
    priority: str | PipePriority | None = None,
) -> PipeTargets:
    """
    Build a normalized PipeTargetsConfig from user input.

    This function accepts multiple declaration styles:
      - Existing ``PipeTargetsConfig`` to optionally override fields.
      - A string or sequence of parameter names.
      - A dict with keys:
          - ``parameters`` or ``bindings``: the target names.
          - ``delimiter``: optional chunk delimiter.
          - ``allow_partial``: optional boolean.
          - ``priority``: 'cli' or 'pipe'

    If more than one target is provided and no delimiter
    is explicitly set, a newline is used by default.
    """
    if isinstance(targets, PipeTargets):
        return _replace_pipe_targets(
            targets,
            delimiter=delimiter,
            allow_partial=allow_partial,
            priority=priority,
        )

    (
        names_value,
        delimiter_explicit,
        final_delimiter,
        allow_partial,
        priority,
    ) = _resolve_pipe_target_inputs(
        targets,
        delimiter=delimiter,
        allow_partial=allow_partial,
        priority=priority,
    )

    names = targets_to_list(names_value)
    if final_delimiter is None and len(names) > 1 and not delimiter_explicit:
        final_delimiter = "\n"

    config = PipeTargets(
        targets=tuple(names),
        delimiter=final_delimiter,
        priority=parse_priority(priority) if priority is not None else "cli",
        allow_partial=allow_partial if allow_partial is not None else False,
    )

    return config


__all__ = ["PipePriority", "PipeTargets", "build_pipe_targets_config"]

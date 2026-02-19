from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal, cast

from objinspect import Parameter
from objinspect.typing import get_literal_choices, type_args
from strto import StrToTypeParser

from interfacy.exceptions import ConfigurationError, PipeInputError
from interfacy.util import is_list_or_list_alias

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
    choices = get_literal_choices(PipePriority)
    if value in choices:
        return cast(PipePriority, value)
    if value is None:
        return "cli"

    raise ConfigurationError(f"Invalid pipe priority '{value}'. Valid values: {','.join(choices)}")


def targets_to_list(value: str | Sequence[object]) -> list[str]:
    """
    Normalize pipe target input into a list of unique names.

    Args:
        value (str | Sequence[object]): String or sequence to normalize.

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


def _replace_pipe_targets(
    config: PipeTargets,
    *,
    delimiter: str | None | object,
    allow_partial: bool | None,
    priority: str | PipePriority | None,
) -> PipeTargets:
    updated = config
    if delimiter is not DELIMITER_UNSET:
        updated = replace(updated, delimiter=cast(str | None, delimiter))
    if allow_partial is not None:
        updated = replace(updated, allow_partial=allow_partial)
    if priority is not None:
        updated = replace(updated, priority=parse_priority(priority))
    return updated


def _resolve_pipe_target_inputs(
    targets: TargetsInput,
    *,
    delimiter: str | None | object,
    allow_partial: bool | None,
    priority: str | PipePriority | None,
) -> tuple[object, bool, str | None, bool | None, str | PipePriority | None]:
    names_value: object = targets
    delimiter_explicit = delimiter is not DELIMITER_UNSET
    final_delimiter: str | None = (
        None if delimiter is DELIMITER_UNSET else cast(str | None, delimiter)
    )
    resolved_allow_partial = allow_partial
    resolved_priority = priority

    if isinstance(targets, dict):
        names_value = targets.get("parameters") or targets.get("bindings")
        if names_value is None:
            raise ConfigurationError(
                "Pipe target dict must include 'parameters' or 'bindings' entries"
            )

        if "delimiter" in targets and delimiter is DELIMITER_UNSET:
            delimiter_explicit = True
            final_delimiter = targets.get("delimiter")

        if resolved_allow_partial is None and "allow_partial" in targets:
            resolved_allow_partial = bool(targets["allow_partial"])

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
    delimiter: str | None | object = DELIMITER_UNSET,
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
        allow_partial=bool(allow_partial) if allow_partial is not None else False,
    )
    return config


def split_data(data: str, config: PipeTargets) -> list[str]:
    """
    Split piped data into chunks based on the target configuration.

    Args:
        data (str): Raw stdin payload.
        config (PipeTargets): Target configuration and delimiter settings.
    """
    expected = len(config.targets)
    if expected <= 1:
        return [data]

    delimiter = config.delimiter
    if delimiter is None:
        pieces = data.splitlines()
    else:
        max_splits = expected - 1 if expected > 0 else -1
        pieces = data.split(delimiter, max_splits) if max_splits >= 0 else data.split(delimiter)

    pieces = [piece.strip() for piece in pieces]
    return pieces


def _split_list_values(chunk: str, delimiter: str | None) -> list[str]:
    values = chunk.splitlines() if delimiter is None else chunk.split(delimiter)
    values = [value.strip() for value in values]
    return values


def is_cli_supplied(value: object, parameter: Parameter) -> bool:
    """
    Check if a value was explicitly provided via CLI.

    For collection types (list, tuple, set), argparse returns an empty collection when nargs='*' and no CLI args are provided.
    """
    if value is None:
        return False

    if parameter.is_typed and _is_empty_collection_from_argparse(value, parameter.type):
        return False

    return not (parameter.has_default and value == parameter.default)


def _is_empty_collection_from_argparse(value: object, param_type: object) -> bool:
    """Check if value is an empty collection from argparse nargs='*'."""
    if value not in ([], (), set()):
        return False

    if is_list_or_list_alias(param_type):
        return True

    origin = getattr(param_type, "__origin__", None)
    if origin in (tuple, set):
        return True
    return param_type in (tuple, set)


def parse_list(
    parameter: Parameter,
    raw: str,
    delimiter: str | None,
    type_parser: StrToTypeParser,
) -> list[Any]:
    """
    Parse a delimited list value into typed elements when possible.

    Args:
        parameter (Parameter): Parameter metadata describing element types.
        raw (str): Raw string value to parse.
        delimiter (str | None): Delimiter for splitting list elements.
        type_parser (StrToTypeParser): Parser registry for converting elements.
    """
    values = _split_list_values(raw, delimiter)
    if not values:
        return []

    element_t: Any | None = None
    if parameter.type is list:
        element_t = str
    else:
        args = type_args(parameter.type)
        if args:
            element_t = args[0]

    parse_func = type_parser.get_parse_func(element_t) if element_t else None
    if parse_func is None:
        return values

    return [parse_func(value) for value in values]


def parse_value(
    parameter: Parameter,
    raw: str,
    delimiter: str | None,
    type_parser: StrToTypeParser,
) -> object:
    """
    Parse a raw string into a typed value for a parameter.

    Args:
        parameter (Parameter): Parameter metadata describing the expected type.
        raw (str): Raw string value to parse.
        delimiter (str | None): Delimiter for list parsing, when applicable.
        type_parser (StrToTypeParser): Parser registry for converting values.
    """
    if parameter.is_typed and is_list_or_list_alias(parameter.type):
        return parse_list(parameter, raw, delimiter, type_parser)

    if not parameter.is_typed:
        return raw

    parse_func = type_parser.get_parse_func(parameter.type)
    if parse_func is None:
        return raw

    return parse_func(raw)


def get_chunks(
    data: str,
    config: PipeTargets,
) -> list[str | None]:
    """
    Split piped data into the configured number of chunks.

    Args:
        data (str): Raw stdin payload.
        config (PipeTargets): Target configuration and delimiter settings.

    Raises:
        PipeInputError: If chunk counts do not match required targets.
    """
    chunks: list[str | None] = cast(list[str | None], split_data(data, config))
    expected = len(config.targets)

    if len(chunks) < expected:
        if not config.allow_partial:
            raise PipeInputError(
                "stdin",
                f"Received {len(chunks)} chunk(s) but {expected} pipe target(s) are configured",
            )
        chunks.extend([None] * (expected - len(chunks)))
    elif len(chunks) > expected:
        raise PipeInputError(
            "stdin",
            f"Received {len(chunks)} chunk(s) but only {expected} pipe target(s) are configured",
        )

    return chunks


def apply_pipe_values(
    data: str,
    *,
    config: PipeTargets,
    arguments: dict[str, Any],
    parameters: dict[str, Parameter],
    type_parser: StrToTypeParser,
) -> dict[str, Any]:
    """Return a new argument mapping with piped stdin applied."""
    updated = dict(arguments)
    chunks = get_chunks(data, config)

    for param_name, raw_chunk in zip(config.targets, chunks, strict=False):
        parameter = parameters.get(param_name)
        if parameter is None:
            raise ConfigurationError(f"Pipe target references unknown parameter '{param_name}'")

        existing = updated.get(param_name)
        cli_supplied = is_cli_supplied(existing, parameter)

        if raw_chunk is None or raw_chunk == "":  # No piped data for this binding
            continue

        try:
            parsed = parse_value(parameter, raw_chunk, config.delimiter, type_parser)
        except Exception as e:
            raise PipeInputError(
                param_name,
                f"failed to convert piped input: {e}",
            ) from e

        priority = config.priority
        if priority == "cli" and cli_supplied:
            continue

        updated[param_name] = parsed

    for param_name in config.targets:
        parameter = parameters.get(param_name)
        if parameter is None:
            continue

        if not parameter.is_required:
            continue

        if updated.get(param_name) is None:
            raise PipeInputError(
                param_name,
                "no piped value was provided and the argument was not supplied on the CLI",
            )

    return updated


__all__ = [
    "PipePriority",
    "PipeTargets",
    "apply_pipe_values",
    "build_pipe_targets_config",
]

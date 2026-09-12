from typing import Any, get_args, get_origin

from objinspect import Parameter
from strto import StrToTypeParser

from interfacy.exceptions import ConfigurationError, PipeInputError
from interfacy.pipe import PipeTargets
from interfacy.schema.typing import is_list_or_list_alias


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
    pieces = data.splitlines() if delimiter is None else data.split(delimiter, expected - 1)

    pieces = [piece.strip() for piece in pieces]

    return pieces


def _split_list_values(chunk: str, delimiter: str | None) -> list[str]:
    values = chunk.splitlines() if delimiter is None else chunk.split(delimiter)
    values = [value.strip() for value in values]
    return values


def is_cli_supplied(
    value: Any,
    parameter: Parameter,
    *,
    present: bool = True,
    cli_supplied_parameters: set[str] | None = None,
) -> bool:
    """
    Check if a value was explicitly provided via CLI.

    For collection types (list, tuple, set), argparse returns an empty collection when nargs='*' and no CLI args are provided.
    """
    if cli_supplied_parameters is not None and parameter.name in cli_supplied_parameters:
        return True

    if not present:
        return False

    if value is None:
        return False

    if parameter.is_typed and _is_empty_collection_from_argparse(value, parameter.type):
        return False

    return not (parameter.has_default and value == parameter.default)


def _is_empty_collection_from_argparse(value: Any, param_type: Any) -> bool:
    """Check if value is an empty collection from argparse nargs='*'."""
    if not isinstance(value, (list, tuple, set)) or len(value) != 0:
        return False

    if is_list_or_list_alias(param_type):
        return True

    origin = get_origin(param_type)
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
        args = get_args(parameter.type)
        if args:
            element_t = args[0]

    try:
        # strto accepts runtime typing forms such as Literal despite its narrow type annotation.
        parse_func = type_parser.get_parse_func(element_t)  # pyrefly: ignore [bad-argument-type]
    except (TypeError, ValueError, AttributeError):
        parse_func = None

    if parse_func is None:
        return values

    return [parse_func(value) for value in values]


def parse_value(
    parameter: Parameter,
    raw: str,
    delimiter: str | None,
    type_parser: StrToTypeParser,
) -> Any:
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

    try:
        # strto accepts runtime typing forms such as unions despite its narrow type annotation.
        parse_func = type_parser.get_parse_func(
            parameter.type  # pyrefly: ignore [bad-argument-type]
        )
    except (TypeError, ValueError, AttributeError):
        parse_func = None

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
    if data == "":
        return [None] * len(config.targets)

    chunks: list[str | None] = list(split_data(data, config))
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


def validate_required_pipe_targets(
    *,
    config: PipeTargets,
    arguments: dict[str, Any],
    parameters: dict[str, Parameter],
    cli_supplied_parameters: set[str] | None = None,
) -> dict[str, Any]:
    """Validate that required pipe targets were supplied by CLI or stdin."""
    updated = dict(arguments)
    for param_name in config.targets:
        parameter = parameters.get(param_name)
        if parameter is None:
            raise ConfigurationError(f"Pipe target references unknown parameter '{param_name}'")

        if not parameter.is_required:
            continue

        if is_cli_supplied(
            updated.get(param_name),
            parameter,
            present=param_name in updated,
            cli_supplied_parameters=cli_supplied_parameters,
        ):
            continue

        raise PipeInputError(
            param_name,
            "no piped value was provided and the argument was not supplied on the CLI",
        )

    return updated


def apply_pipe_values(
    data: str,
    *,
    config: PipeTargets,
    arguments: dict[str, Any],
    parameters: dict[str, Parameter],
    type_parser: StrToTypeParser,
    cli_supplied_parameters: set[str] | None = None,
) -> dict[str, Any]:
    """Return a new argument mapping with piped stdin applied."""
    updated = dict(arguments)
    chunks = get_chunks(data, config)

    for param_name, raw_chunk in zip(config.targets, chunks, strict=False):
        parameter = parameters.get(param_name)
        if parameter is None:
            raise ConfigurationError(f"Pipe target references unknown parameter '{param_name}'")

        existing = updated.get(param_name)
        cli_supplied = is_cli_supplied(
            existing,
            parameter,
            present=param_name in updated,
            cli_supplied_parameters=cli_supplied_parameters,
        )

        if raw_chunk is None or raw_chunk == "":  # No piped data for this binding
            continue

        if config.priority == "cli" and cli_supplied:
            continue

        try:
            parsed = parse_value(parameter, raw_chunk, config.delimiter, type_parser)
        except Exception as e:
            raise PipeInputError(
                param_name,
                f"failed to convert piped input: {e}",
            ) from e

        updated[param_name] = parsed

    return validate_required_pipe_targets(
        config=config,
        arguments=updated,
        parameters=parameters,
        cli_supplied_parameters=cli_supplied_parameters,
    )

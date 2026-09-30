from __future__ import annotations

from typing import Any

from interfacy.common.sentinels import MODEL_DEFAULT_UNSET
from interfacy.models import (
    build_model_instance,
    is_model_type,
    model_fields_for_expansion,
    model_instance_to_values,
    unwrap_optional,
)
from interfacy.schema.model import Argument


class ExpandedModelValidationError(ValueError):
    """Raised when expanded model flags are incomplete for reconstruction."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def reconstruct_expanded_models(
    args: dict[str, Any],
    arguments: list[Argument],
) -> dict[str, Any]:
    """
    Rebuild expanded model parameters from flattened argument values.

    Args:
        args (dict[str, Any]): Parsed command arguments to mutate and normalize.
        arguments (list[Argument]): Command argument schemas with expansion metadata.

    Raises:
        ExpandedModelValidationError: A provided model is missing required fields.
    """
    grouped = group_expanded_arguments(arguments)
    if not grouped:
        return args

    for root_name, group in grouped.items():
        _reconstruct_group(args, root_name, group)

    return args


def group_expanded_arguments(arguments: list[Argument]) -> dict[str, list[Argument]]:
    """
    Group expanded arguments by the model parameter they were flattened from.

    Args:
        arguments (list[Argument]): Command argument schemas.
    """
    grouped: dict[str, list[Argument]] = {}
    for arg in arguments:
        if arg.is_expanded_from is None:
            continue

        grouped.setdefault(arg.is_expanded_from, []).append(arg)

    return grouped


def validate_required_model_values(
    model_type: type,
    group: list[Argument],
    values: dict[str, Any],
    provided_paths: set[tuple[str, ...]],
) -> None:
    """
    Raise when provided model values leave required fields without a value.

    Args:
        model_type (type): Root model type.
        group (list[Argument]): Expanded arguments of the root model parameter.
        values (dict[str, Any]): Nested field values collected for the model.
        provided_paths (set[tuple[str, ...]]): Expansion paths given on the command line.

    Raises:
        ExpandedModelValidationError: Required field flags are missing.
    """
    missing = _missing_required_flags(
        model_type,
        values,
        path=(group[0].is_expanded_from or "",),
        group=group,
    )
    if not missing:
        return

    trigger = _provided_context_flag(provided_paths, group)
    missing_text = ", ".join(missing)
    if trigger is None:
        message = f"the following arguments are required: {missing_text}"
    else:
        message = f"the following arguments are required when {trigger} is provided: {missing_text}"

    raise ExpandedModelValidationError(message)


def _reconstruct_group(args: dict[str, Any], root_name: str, group: list[Argument]) -> None:
    model_type = group[0].original_model_type
    if model_type is None:
        return
    if root_name in args and not any(arg.name in args for arg in group):
        return

    model_default = group[0].model_default
    has_model_default = model_default is not MODEL_DEFAULT_UNSET
    values, provided, provided_paths = _collect_model_values(args, group)
    args[root_name] = _reconstructed_model_value(
        model_type,
        group,
        values,
        provided,
        provided_paths,
        model_default,
        has_model_default,
    )

    for arg in group:
        args.pop(arg.name, None)


def _reconstructed_model_value(
    model_type: type,
    group: list[Argument],
    values: dict[str, Any],
    provided: bool,
    provided_paths: set[tuple[str, ...]],
    model_default: Any,
    has_model_default: bool,
) -> Any:
    if not provided:
        if has_model_default:
            return model_default
        if any(arg.parent_is_optional for arg in group):
            return None

        return build_model_instance(model_type, values)

    if has_model_default and model_default is not None:
        base_values = model_instance_to_values(model_type, model_default)
        merged = _deep_merge(base_values, values)
        validate_required_model_values(model_type, group, merged, provided_paths)

        return build_model_instance(model_type, merged)

    validate_required_model_values(model_type, group, values, provided_paths)

    return build_model_instance(model_type, values)


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value

    return merged


def _collect_model_values(
    args: dict[str, Any],
    expanded_args: list[Argument],
) -> tuple[dict[str, Any], bool, set[tuple[str, ...]]]:
    values: dict[str, Any] = {}
    provided = False
    provided_paths: set[tuple[str, ...]] = set()

    for arg in expanded_args:
        if arg.name not in args:
            continue

        provided = True

        if arg.expansion_path:
            provided_paths.add(arg.expansion_path)
        path = arg.expansion_path[1:] if arg.expansion_path else ()
        if not path:
            continue

        current = values
        for part in path[:-1]:
            current = current.setdefault(part, {})

        current[path[-1]] = args[arg.name]

    return values, provided, provided_paths


def _missing_required_flags(
    model_type: type,
    values: dict[str, Any],
    *,
    path: tuple[str, ...],
    group: list[Argument],
) -> list[str]:
    missing: list[str] = []
    for field in model_fields_for_expansion(model_type):
        field_path = (*path, field.name)
        if field.name not in values:
            if field.required:
                missing.extend(_required_leaf_flags(field.annotation, field_path, group))

            continue

        value = values[field.name]
        inner, _ = unwrap_optional(field.annotation)
        if isinstance(value, dict) and is_model_type(inner):
            missing.extend(_missing_required_flags(inner, value, path=field_path, group=group))

    return _dedupe_preserving_order(missing)


def _required_leaf_flags(
    annotation: Any,
    path: tuple[str, ...],
    group: list[Argument],
) -> list[str]:
    flag = _flag_for_path(group, path)
    if flag is not None:
        return [flag]

    inner, _ = unwrap_optional(annotation)
    if not is_model_type(inner):
        return []

    flags: list[str] = []
    for field in model_fields_for_expansion(inner):
        if field.required:
            flags.extend(_required_leaf_flags(field.annotation, (*path, field.name), group))

    return _dedupe_preserving_order(flags)


def _flag_for_path(group: list[Argument], path: tuple[str, ...]) -> str | None:
    for arg in group:
        if arg.expansion_path == path and arg.flags:
            return arg.flags[0]

    return None


def _provided_context_flag(
    provided_paths: set[tuple[str, ...]],
    group: list[Argument],
) -> str | None:
    best: tuple[int, str] | None = None
    for arg in group:
        if arg.expansion_path not in provided_paths or not arg.flags:
            continue

        candidate = (len(arg.expansion_path), arg.flags[0])
        if best is None or candidate[0] > best[0]:
            best = candidate

    return best[1] if best is not None else None


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


__all__ = [
    "ExpandedModelValidationError",
    "group_expanded_arguments",
    "reconstruct_expanded_models",
    "validate_required_model_values",
]

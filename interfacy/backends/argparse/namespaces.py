from __future__ import annotations

import argparse
from argparse import Namespace
from collections.abc import Mapping, Sequence
from typing import Any

from interfacy.common.debug import get_logger

logger = get_logger(__name__)

DEST_KEY = "dest"


def namespace_to_dict(namespace: Namespace) -> dict[str, Any]:
    """
    Convert an argparse Namespace into a nested dictionary.

    Args:
        namespace (Namespace): Parsed namespace to convert.
    """
    result = {}
    for k, v in vars(namespace).items():
        if isinstance(v, Namespace):
            result[k] = namespace_to_dict(v)
        else:
            result[k] = v

    return result


def supplied_to_dict(
    namespace: Namespace,
    supplied_dests: set[str],
    separator: str,
) -> dict[str, Any]:
    """
    Convert a deflattened namespace into a nested dictionary of supplied values only.

    Nested namespaces are always kept, so the result has the same buckets as
    ``namespace_to_dict(namespace)``.

    Args:
        namespace (Namespace): Deflattened namespace to convert.
        supplied_dests (set[str]): Flat destinations given on the command line.
        separator (str): Separator joining nested destination components.
    """
    paths = {tuple(dest.split(separator)) for dest in supplied_dests}

    def convert(current: Namespace, prefix: tuple[str, ...]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in vars(current).items():
            path = (*prefix, key)
            if isinstance(value, Namespace):
                result[key] = convert(value, path)
            elif path in paths:
                result[key] = value

        return result

    return convert(namespace, ())


def deflatten_namespace(namespace: Namespace, separator: str) -> Namespace:
    """
    Expand separator-joined destination keys into nested namespaces.

    Args:
        namespace (Namespace): Flat namespace produced by argparse.
        separator (str): Separator joining nested destination components.

    Raises:
        ValueError: If two keys resolve to conflicting values at the same path.
    """
    root = Namespace()

    for key, value in vars(namespace).items():
        components = key.split(separator)
        current = root

        # Navigate through component hierarchy
        for component in components[:-1]:
            if not hasattr(current, component):
                logger.debug("Creating new namespace for '%s'", component)
                setattr(current, component, Namespace())

            current = getattr(current, component)

        # Set or merge final value
        final_component = components[-1]
        if hasattr(current, final_component):
            logger.debug("Merging nested namespaces at %s", final_component)
            existing_value = getattr(current, final_component)
            if isinstance(existing_value, Namespace) and isinstance(value, Namespace):
                merge_namespaces(existing_value, value)
            else:
                raise ValueError(f'Cannot merge namespaces due to conflict at key "{key}"')
        else:
            setattr(current, final_component, value)

    return root


def merge_namespaces(destination: Namespace, source: Namespace) -> Namespace:
    """
    Recursively merge ``source`` into ``destination`` in place.

    Args:
        destination (Namespace): Namespace receiving attributes.
        source (Namespace): Namespace whose attributes are merged.

    Raises:
        ValueError: If both namespaces define a non-namespace value for the same attribute.
    """
    for name, value in vars(source).items():
        if hasattr(destination, name):
            dest_value = getattr(destination, name)
            if isinstance(dest_value, Namespace) and isinstance(value, Namespace):
                logger.info("Recursively merging at attribute: %s", name)
                merge_namespaces(dest_value, value)
            else:
                raise ValueError(f'Cannot merge namespaces due to conflict at attribute "{name}".')
        else:
            logger.info("Setting new attribute: %s", name)
            setattr(destination, name, value)

    return destination


def nested_destination(dest: str, nest_path: Sequence[str], separator: str) -> str:
    """
    Prefix a destination with the parser's nesting path.

    Args:
        dest (str): Original destination name.
        nest_path (Sequence[str]): Nesting path components of the owning parser.
        separator (str): Separator joining nested destination components.
    """
    if not nest_path:
        return dest

    nested = f"{separator.join(nest_path)}{separator}{dest}"
    logger.info("Generated nested dest: %s -> %s", nested, dest)

    return nested


def original_destination(dest: str, originals: Mapping[str, str], separator: str) -> str:
    """
    Resolve a nested destination back to its original name.

    Args:
        dest (str): Possibly nested destination name.
        originals (Mapping[str, str]): Known nested-to-original destination mapping.
        separator (str): Separator joining nested destination components.
    """
    original = originals.get(dest)
    if original is not None:
        return original
    if separator in dest:
        return dest.rsplit(separator, maxsplit=1)[-1]

    return dest


def extract_destination(
    option_strings: Sequence[str],
    dest: Any,
    prefix_chars: str,
) -> str:
    """
    Derive an optional argument's destination the way argparse does.

    Args:
        option_strings (Sequence[str]): Option strings passed to ``add_argument``.
        dest (Any): Explicit ``dest`` keyword value, if any.
        prefix_chars (str): Prefix characters of the owning parser.
    """
    if dest is not None:
        return str(dest)
    # Find first long option string, falling back to first short option
    candidates = ((s, len(s) > 2) for s in option_strings if s[0] in prefix_chars)
    for option_string, is_long in candidates:
        if is_long and option_string[1] in prefix_chars:
            logger.debug("Using long option string for dest: %s", option_string)
            return option_string.lstrip(prefix_chars)
    # If no long option found, use first short option
    short_dest = next(s.lstrip(prefix_chars) for s in option_strings if s[0] in prefix_chars)
    logger.debug("Using short option string for dest: %s", short_dest)

    return short_dest


def container_defaults(container: argparse._ActionsContainer) -> dict[str, Any]:
    """
    Return the defaults mapping stored on an argparse action container.

    Args:
        container (argparse._ActionsContainer): Parser or argument group.
    """
    defaults = getattr(container, "_defaults", None)
    if isinstance(defaults, dict):
        return defaults

    return {}


def container_actions(container: argparse._ActionsContainer) -> list[argparse.Action]:
    """
    Return the actions registered on an argparse action container.

    Args:
        container (argparse._ActionsContainer): Parser or argument group.
    """
    actions = getattr(container, "_actions", ())
    if not isinstance(actions, list):
        actions = list(actions)

    return [action for action in actions if isinstance(action, argparse.Action)]


__all__ = [
    "DEST_KEY",
    "container_actions",
    "container_defaults",
    "deflatten_namespace",
    "extract_destination",
    "merge_namespaces",
    "namespace_to_dict",
    "nested_destination",
    "original_destination",
    "supplied_to_dict",
]

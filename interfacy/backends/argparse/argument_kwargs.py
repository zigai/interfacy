from __future__ import annotations

from typing import Any

from objinspect.typing import type_name


def _safe_type_name(target: Any) -> str:
    try:
        return type_name(target)
    except (AttributeError, TypeError, ValueError):
        return str(target)


def callable_type_name(value: Any, *, fallback: str = "value") -> str:
    """
    Return a readable type name for an argparse ``type`` callable.

    Args:
        value (Any): Parser callable, type, or partial wrapping a type.
        fallback (str): Name returned when ``value`` is None.
    """
    if value is None:
        return fallback

    name = getattr(value, "__name__", None)
    if isinstance(name, str) and name:
        return name

    parsed_type = getattr(value, "_t", None)
    if parsed_type is not None:
        return _safe_type_name(parsed_type)

    keywords = getattr(value, "keywords", None)
    if isinstance(keywords, dict) and keywords.get("t") is not None:
        return _safe_type_name(keywords["t"])

    return _safe_type_name(value)


NO_METAVAR_ACTIONS = frozenset(
    {
        "store_true",
        "store_false",
        "store_const",
        "append_const",
        "count",
        "help",
        "version",
        "BooleanOptionalAction",
    }
)


def set_callable_type_name(value: Any) -> None:
    """
    Give an unnamed parser callable a ``__name__`` for argparse error messages.

    Args:
        value (Any): Parser callable passed as an argparse ``type``.
    """
    if not callable(value) or getattr(value, "__name__", None):
        return

    try:
        value.__name__ = callable_type_name(value)  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        pass


def normalize_argument_kwargs(
    original_dest: str,
    nest_separator: str,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """
    Name the ``type`` callable and default the metavar of ``add_argument`` keywords.

    Args:
        original_dest (str): Destination name before nesting.
        nest_separator (str): Separator joining nested destination components.
        kwargs (dict[str, Any]): Keyword arguments passed to ``add_argument``; updated in place.
    """
    set_callable_type_name(kwargs.get("type"))

    action = kwargs.get("action", "store")
    action_name = action if isinstance(action, str) else getattr(action, "__name__", "")
    if action_name in NO_METAVAR_ACTIONS or "metavar" in kwargs:
        return kwargs

    dest_for_metavar = original_dest
    if nest_separator in dest_for_metavar:
        dest_for_metavar = dest_for_metavar.split(nest_separator)[-1]

    kwargs["metavar"] = dest_for_metavar.replace("_", "-").upper()

    return kwargs


__all__ = [
    "NO_METAVAR_ACTIONS",
    "callable_type_name",
    "normalize_argument_kwargs",
    "set_callable_type_name",
]

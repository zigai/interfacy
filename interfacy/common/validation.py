from __future__ import annotations

from typing import Any

ValidationIssue = tuple[tuple[str | int, ...], str]


def validation_issues(error: BaseException) -> list[ValidationIssue] | None:
    """
    Return the field path and message of each failure in a Pydantic validation error.

    The rejected input is left out, unlike in ``str(error)``, so the result is safe to print.

    Args:
        error (BaseException): Exception to inspect.

    Returns:
        The failures, or ``None`` when ``error`` is not a Pydantic validation error.
    """
    error_type = type(error)
    package = error_type.__module__.partition(".")[0]
    if error_type.__name__ != "ValidationError" or package not in {"pydantic", "pydantic_core"}:
        return None

    pydantic_error: Any = error

    return [(tuple(issue["loc"]), issue["msg"]) for issue in pydantic_error.errors()]


def format_validation_issue(issue: ValidationIssue) -> str:
    """
    Format one failure as ``field.path: message``.

    Args:
        issue (ValidationIssue): Field path and message.
    """
    path, message = issue
    return f"{'.'.join(str(part) for part in path)}: {message}" if path else message


__all__ = ["ValidationIssue", "format_validation_issue", "validation_issues"]

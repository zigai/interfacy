from __future__ import annotations

import sys
import traceback

from stdl.st import colored


def info(message: str) -> None:
    print(message, file=sys.stdout)


def warn(message: str) -> None:
    print(message, file=sys.stderr)


def error(message: str) -> None:
    print(message, file=sys.stderr)


def log(tag: str, message: str) -> None:
    info(f"[{tag}] {message}")


def log_error(tag: str, message: str) -> None:
    formatted = colored(f"[{tag}] {message}", color="red")
    error(formatted)


def log_exception(tag: str, exc: BaseException, *, full_traceback: bool) -> None:
    del tag

    if full_traceback:
        error("".join(traceback.format_exception(exc)).rstrip())

    exception_str = f"{type(exc).__name__}: {exc}"
    message = colored(exception_str, color="red")
    error(message)


def log_interrupt(*, silent: bool) -> None:
    if silent:
        return

    message = colored("\nInterrupted", color="yellow")
    error(message)


__all__ = [
    "error",
    "info",
    "log",
    "log_error",
    "log_exception",
    "log_interrupt",
    "warn",
]

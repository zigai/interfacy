from __future__ import annotations

import sys
import traceback
from collections.abc import Callable
from typing import Any

from objinspect.typing import type_name
from stdl.st import colored, terminal_link


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


def log_exception(tag: str, exc: Exception, *, full_traceback: bool) -> None:
    if full_traceback:
        error(traceback.format_exc())

    message = ""
    tb = exc.__traceback__

    exception_str = type_name(str(type(exc))) + ": " + str(exc)
    if tb:
        file_info = f"{terminal_link(tb.tb_frame.f_code.co_filename)}:{tb.tb_lineno}"
        message += file_info
        message += " "

    message += f"{colored(exception_str, color='red')}"
    message = f"[{tag}] {message}"
    message = colored(message, color="red")
    error(message)


def log_interrupt(tag: str, *, silent: bool) -> None:
    if silent:
        return
    message = f"[{tag}] Interrupted"
    message = colored(message, color="yellow")
    error(message)


def display_result(value: Any, handler: Callable = print) -> None:
    if isinstance(value, list):
        for entry in value:
            handler(entry)
    elif isinstance(value, dict):
        from pprint import pprint

        pprint(value)
    else:
        handler(value)


__all__ = [
    "info",
    "warn",
    "error",
    "log",
    "log_error",
    "log_exception",
    "log_interrupt",
    "display_result",
]

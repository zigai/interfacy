from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from interfacy.console import log, log_error, log_exception, log_interrupt


@dataclass
class RuntimePolicy:
    display_result: bool
    result_display_fn: Callable[[Any], Any]
    full_error_traceback: bool
    on_interrupt: Callable[[KeyboardInterrupt], None] | None
    silent_interrupt: bool
    logger_message_tag: str = "interfacy"

    def display(self, value: Any) -> None:
        if self.display_result:
            self.result_display_fn(value)

    def handle_interrupt(self, e: KeyboardInterrupt) -> None:
        if self.on_interrupt is not None:
            self.on_interrupt(e)

        self.log_interrupt()

    def log(self, message: str) -> None:
        log(self.logger_message_tag, message)

    def log_error(self, message: str) -> None:
        log_error(self.logger_message_tag, message)

    def log_exception(self, e: BaseException) -> None:
        log_exception(self.logger_message_tag, e, full_traceback=self.full_error_traceback)

    def log_interrupt(self) -> None:
        log_interrupt(silent=self.silent_interrupt)


__all__ = ["RuntimePolicy"]

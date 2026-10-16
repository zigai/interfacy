from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from interfacy.common.console import log, log_error, log_exception, log_interrupt
from interfacy.common.terminal import get_terminal_width
from interfacy.exceptions import ParseDiagnostic, UsageError
from interfacy.help.diagnostics import (
    DiagnosticLayout,
    build_diagnostic_content,
    normalize_diagnostic_text,
)


@dataclass
class RuntimePolicy:
    display_result: bool
    result_display_fn: Callable[[Any], Any]
    full_error_traceback: bool
    on_interrupt: Callable[[KeyboardInterrupt], None] | None
    silent_interrupt: bool
    logger_message_tag: str = "interfacy"
    diagnostic_renderer: Callable[[UsageError], str] | None = None

    def display(self, value: Any) -> None:
        if self.display_result:
            self.result_display_fn(value)

    def handle_interrupt(self, e: BaseException) -> None:
        if self.on_interrupt is not None and isinstance(e, KeyboardInterrupt):
            self.on_interrupt(e)

        self.log_interrupt()

    def format_diagnostic(self, failure: UsageError) -> str:
        if self.diagnostic_renderer is not None:
            return normalize_diagnostic_text(self.diagnostic_renderer(failure))

        diagnostic = failure.diagnostic or ParseDiagnostic(kind="usage", message=str(failure))
        content = build_diagnostic_content(
            diagnostic,
            program=failure.program or Path(sys.argv[0]).name,
            help_flags=(),
            usage=failure.usage,
        )

        return normalize_diagnostic_text(
            DiagnosticLayout().render(content, terminal_width=get_terminal_width())
        )

    def log(self, message: str) -> None:
        log(self.logger_message_tag, message)

    def log_error(self, message: str) -> None:
        log_error(self.logger_message_tag, message)

    def log_exception(self, e: BaseException) -> None:
        log_exception(self.logger_message_tag, e, full_traceback=self.full_error_traceback)

    def log_interrupt(self) -> None:
        log_interrupt(silent=self.silent_interrupt)


__all__ = ["RuntimePolicy"]

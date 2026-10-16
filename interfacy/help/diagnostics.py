from __future__ import annotations

import os
import sys
import textwrap
from dataclasses import dataclass, field
from difflib import get_close_matches
from typing import Literal

from stdl.st import TextStyle, with_style

from interfacy.common.terminal import strip_ansi
from interfacy.exceptions import DiagnosticKind, ParseDiagnostic

DiagnosticSection = Literal["message", "suggestions", "choices", "hints", "usage", "help"]


@dataclass(frozen=True, kw_only=True)
class DiagnosticContent:
    """Display content that plugins may transform without changing the parse failure."""

    message: str
    suggestions: tuple[str, ...] = ()
    choices: tuple[str, ...] = ()
    choices_heading: str = "Valid choices:"
    hints: tuple[str, ...] = ()
    usage: str | None = None
    help_command: str | None = None
    help_text: str | None = None


@dataclass(frozen=True)
class DiagnosticResult:
    """Final diagnostic text returned by a plugin renderer."""

    text: str


def diagnostic_message(diagnostic: ParseDiagnostic) -> str:
    if diagnostic.message:
        return diagnostic.message

    argument = repr(diagnostic.argument) if diagnostic.argument else "argument"
    expected = diagnostic.expected or "a valid value"
    messages: dict[DiagnosticKind, str] = {
        "unknown_command": f"unknown command {diagnostic.token!r}",
        "unknown_option": f"unknown option {diagnostic.argument!r}",
        "missing_argument": f"missing required argument {argument}",
        "missing_value": f"{argument} requires a value",
        "missing_subcommand": (
            f"a command is required; available commands: {', '.join(diagnostic.choices)}"
            if diagnostic.choices
            else "a command is required"
        ),
        "invalid_choice": f"invalid choice for {argument}",
        "invalid_type": f"{argument} requires {expected}",
        "unexpected_argument": "unexpected argument",
        "usage": "invalid command-line input",
    }
    return messages[diagnostic.kind]


def build_diagnostic_content(
    diagnostic: ParseDiagnostic,
    *,
    program: str,
    help_flags: tuple[str, ...],
    usage: str | None = None,
) -> DiagnosticContent:
    suggestions: tuple[str, ...] = ()
    choices: tuple[str, ...] = ()
    heading = "Valid choices:"
    if diagnostic.kind in ("unknown_command", "unknown_option"):
        token = diagnostic.token if diagnostic.kind == "unknown_command" else diagnostic.argument
        if token:
            suggestions = tuple(get_close_matches(token, diagnostic.choices))

        if diagnostic.kind == "unknown_command" and not suggestions:
            choices = diagnostic.choices
            heading = "Available commands:"
    elif diagnostic.kind == "invalid_choice":
        choices = diagnostic.choices

    show_usage = diagnostic.kind in (
        "missing_argument",
        "missing_value",
        "invalid_choice",
        "invalid_type",
        "unexpected_argument",
        "usage",
    )

    return DiagnosticContent(
        message=diagnostic_message(diagnostic),
        suggestions=suggestions,
        choices=choices,
        choices_heading=heading,
        usage=usage if show_usage else None,
        help_command=f"{program} {help_flags[0]}" if help_flags else None,
        help_text=usage if diagnostic.kind == "missing_subcommand" else None,
    )


@dataclass(kw_only=True)
class DiagnosticLayout:
    """Arrange diagnostics independently of help; omitted sections are not displayed."""

    error_prefix: str = "error:"
    suggestions_heading: str = "Did you mean"
    sections: tuple[DiagnosticSection, ...] = (
        "message",
        "suggestions",
        "choices",
        "hints",
        "usage",
        "help",
    )
    indent: str = ""
    message_spacing: str = "\n\n"
    section_spacing: str = "\n"
    error_style: TextStyle = field(default_factory=lambda: TextStyle(color="red", style="bold"))
    hint_style: TextStyle = field(default_factory=lambda: TextStyle(style="dim"))

    def render(self, content: DiagnosticContent, *, terminal_width: int) -> str:
        if content.help_text:
            return content.help_text.rstrip() + "\n"

        colored = (
            sys.stderr.isatty()
            and "NO_COLOR" not in os.environ
            and "NOCOLOR" not in os.environ
            and os.environ.get("TERM") != "dumb"
        )
        prefix = self.error_prefix
        sections: dict[DiagnosticSection, str] = {
            "message": f"{prefix} {content.message}",
            "suggestions": (
                f"{self.suggestions_heading} {', '.join(repr(item) for item in content.suggestions)}?"
                if content.suggestions
                else ""
            ),
            "choices": (
                f"{content.choices_heading} {', '.join(content.choices)}" if content.choices else ""
            ),
            "hints": "\n".join(content.hints),
            "usage": content.usage.rstrip() if content.usage else "",
            "help": (f"Run '{content.help_command}' for usage." if content.help_command else ""),
        }
        rendered = ""
        previous: DiagnosticSection | None = None

        for section in self.sections:
            text = sections[section]
            if not text:
                continue

            wrapped = "\n".join(
                textwrap.fill(
                    line,
                    width=terminal_width,
                    initial_indent=self.indent,
                    subsequent_indent=self.indent + "  ",
                    break_long_words=False,
                    break_on_hyphens=False,
                )
                for line in text.splitlines()
            )
            if colored and section == "message":
                wrapped = wrapped.replace(prefix, with_style(prefix, self.error_style), 1)

            if colored and section == "help":
                wrapped = with_style(wrapped, self.hint_style)

            if rendered:
                rendered += self.message_spacing if previous == "message" else self.section_spacing

            rendered += wrapped
            previous = section

        return rendered.rstrip() + "\n"


def normalize_diagnostic_text(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("diagnostic renderers must return str")

    if (
        not sys.stderr.isatty()
        or "NO_COLOR" in os.environ
        or "NOCOLOR" in os.environ
        or os.environ.get("TERM") == "dumb"
    ):
        text = strip_ansi(text)

    return text.rstrip("\r\n") + "\n"


__all__ = [
    "DiagnosticContent",
    "DiagnosticLayout",
    "DiagnosticResult",
    "DiagnosticSection",
    "build_diagnostic_content",
    "diagnostic_message",
    "normalize_diagnostic_text",
]

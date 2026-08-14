from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from interfacy.schema.schema import Command, ParserSchema

HelpSectionKind = Literal[
    "usage",
    "description",
    "positionals",
    "options",
    "commands",
    "epilog",
]


@dataclass(frozen=True)
class HelpSection:
    """One semantic block in a help document."""

    kind: HelpSectionKind
    text: str


@dataclass(frozen=True)
class HelpContent:
    """Backend-neutral help document produced before terminal rendering."""

    sections: tuple[HelpSection, ...]


@dataclass(frozen=True)
class HelpContext:
    """Stable context describing the help document being rendered."""

    prog: str
    terminal_width: int
    schema: ParserSchema | None = None
    command: Command | None = None


@dataclass(frozen=True)
class HelpResult:
    """Final help text returned by the first plugin renderer that handles help."""

    text: str


class HelpRenderer(Protocol):
    """Backend-neutral final help renderer."""

    def __call__(self, context: HelpContext, content: HelpContent) -> str:
        """Render transformed structured help without output normalization."""
        ...


def normalize_help_text(text: str) -> str:
    """Return help text with exactly one trailing newline."""
    if not isinstance(text, str):
        raise TypeError("help renderers must return str")
    return text.rstrip("\r\n") + "\n"


def default_help_renderer(context: HelpContext, content: HelpContent) -> str:
    """Join nonempty structured help sections."""
    del context
    return "\n\n".join(section.text.rstrip("\n") for section in content.sections if section.text)


def render_help_content(
    context: HelpContext,
    content: HelpContent,
    renderer: HelpRenderer | None = None,
) -> str:
    """Render structured help once and normalize its terminal newline."""
    final_renderer = renderer or default_help_renderer
    return normalize_help_text(final_renderer(context, content))


HelpContentTransform = Callable[[HelpContext, HelpContent], HelpContent]


__all__ = [
    "HelpContent",
    "HelpContentTransform",
    "HelpContext",
    "HelpRenderer",
    "HelpResult",
    "HelpSection",
    "HelpSectionKind",
    "default_help_renderer",
    "normalize_help_text",
    "render_help_content",
]

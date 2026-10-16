from __future__ import annotations

from dataclasses import dataclass, field

import click

from interfacy.backends.base import NativePresentation
from interfacy.exceptions import ParseDiagnostic
from interfacy.help.diagnostics import diagnostic_message


class ClickParseError(click.BadParameter):
    """Carry safe failure facts from the exact Click operation that rejected input."""

    def __init__(
        self,
        diagnostic: ParseDiagnostic,
        *,
        ctx: click.Context | None = None,
        param: click.Parameter | None = None,
    ) -> None:
        self.diagnostic = diagnostic
        super().__init__(diagnostic_message(diagnostic), ctx=ctx, param=param)


class ClickParseContext(click.Context):
    """Keep parser-produced state local to a single command context."""

    interfacy_has_extra_args: bool = False


@dataclass(slots=True, kw_only=True)
class ClickPresentation(NativePresentation):
    """Retain the failing invocation context without retaining its exception."""

    context: click.Context | None = field(default=None, repr=False, compare=False)


def argument_label(parameter: click.Parameter) -> str:
    if isinstance(parameter, click.Option):
        return next(
            (flag for flag in parameter.opts if flag.startswith("--")),
            parameter.opts[0] if parameter.opts else parameter.name or "argument",
        )

    return (parameter.name or "argument").replace("_", "-")


__all__ = ["ClickParseContext", "ClickParseError", "ClickPresentation", "argument_label"]

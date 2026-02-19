from __future__ import annotations

from collections.abc import Callable, Sequence
from os import get_terminal_size
from typing import Any

import click


class ClickHelpFormatter(click.HelpFormatter):
    def __init__(
        self,
        indent_increment: int = 2,
        width: int | None = None,
        max_width: int | None = None,  # noqa: ARG002 - click formatter signature
    ) -> None:
        try:
            terminal_width = get_terminal_size()[0]
        except OSError:
            terminal_width = 80
        super().__init__(indent_increment, width, terminal_width)


click.Context.formatter_class = ClickHelpFormatter


class ClickFuncParamType(click.types.FuncParamType):
    def __init__(self, func: Callable[[Any], Any], name: str | None = None) -> None:
        self.func = func
        raw_name = name if name is not None else getattr(func, "__name__", None)
        self.name = str(raw_name) if raw_name is not None else "NO_NAME"


class ChoiceParamType(click.ParamType):
    name = "choice"

    def __init__(self, choices: Sequence[Any], parser: Callable[[str], Any] | None = None) -> None:
        self.choices = tuple(choices)
        self.parser = parser
        self._parsed_choices: tuple[Any, ...] | None = None
        if self.parser is not None:
            try:
                self._parsed_choices = tuple(self.parser(choice) for choice in self.choices)
            except (TypeError, ValueError, click.BadParameter):
                self._parsed_choices = None

    def convert(
        self, value: str, param: click.Parameter | None, ctx: click.Context | None
    ) -> object:
        converted: Any = value
        if self.parser is not None:
            try:
                converted = self.parser(value)
            except (TypeError, ValueError, click.BadParameter) as exc:
                raise click.BadParameter(str(exc), ctx=ctx, param=param) from exc

        allowed = self._parsed_choices if self._parsed_choices is not None else self.choices
        if converted not in allowed:
            choices_repr = ", ".join(repr(choice) for choice in self.choices)
            raise click.BadParameter(
                f"invalid choice: {value!r} (choose from {choices_repr})",
                ctx=ctx,
                param=param,
            )
        return converted


__all__ = ["ChoiceParamType", "ClickFuncParamType", "ClickHelpFormatter"]

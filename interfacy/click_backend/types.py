from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import click


class ClickFuncParamType(click.types.FuncParamType):
    """Wrap a callable parser as a Click parameter type."""

    def __init__(self, func: Callable[[Any], Any], name: str | None = None) -> None:
        self.func = func
        raw_name = name if name is not None else getattr(func, "__name__", None)
        self.name = str(raw_name) if raw_name is not None else "NO_NAME"

    def convert(self, value: Any, param: click.Parameter | None, ctx: click.Context | None) -> Any:
        try:
            return self.func(value)
        except (ValueError, TypeError, KeyError) as exc:
            self.fail(f"invalid value for configured type parser: {exc}", param, ctx)


class ChoiceParamType(click.ParamType):
    """Validate values against a fixed choice set with optional pre-parsing."""

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

    def convert(self, value: str, param: click.Parameter | None, ctx: click.Context | None) -> Any:
        """
        Convert and validate one CLI value against configured choices.

        Args:
            value (str): Raw CLI token.
            param (click.Parameter | None): Click parameter metadata.
            ctx (click.Context | None): Active Click context.

        Raises:
            click.BadParameter: If conversion fails or value is not in the allowed set.
        """
        converted: Any = value
        if self.parser is not None:
            try:
                converted = self.parser(value)
            except (TypeError, ValueError, KeyError, click.BadParameter):
                converted = value
        allowed = self._parsed_choices if self._parsed_choices is not None else self.choices
        if converted not in allowed:
            choices_repr = ", ".join(repr(choice) for choice in self.choices)
            raise click.BadParameter(
                f"invalid choice: {value!r} (choose from {choices_repr})",
                ctx=ctx,
                param=param,
            )

        return converted


__all__ = ["ChoiceParamType", "ClickFuncParamType"]

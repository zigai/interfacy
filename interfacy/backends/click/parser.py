from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

import click
import click.parser as click_parser


class OptionLike(Protocol):
    nargs: int


class ParsingStateLike(Protocol):
    largs: list[str]
    rargs: list[str]


def _click_parser_symbol(name: str) -> Any:
    """Load a click.parser symbol by name without direct private-member access."""
    try:
        return getattr(click_parser, name)
    except AttributeError as exc:  # pragma: no cover - Click internals unexpectedly changed
        raise RuntimeError(f"Unsupported Click parser internals: missing {name!r}.") from exc


_BaseOptionParser: type[Any] = _click_parser_symbol("_OptionParser")
_normalize_opt: Callable[[str, Any], str] = _click_parser_symbol("_normalize_opt")


class InterfacyOptionParser(_BaseOptionParser):
    """Parse Click options while supporting varargs option values."""

    def _token_looks_like_option(self, arg_text: str) -> bool:
        if arg_text == "--":
            return True
        if not arg_text or arg_text[:1] not in self._opt_prefixes or len(arg_text) == 1:
            return False

        option_token = arg_text.split("=", 1)[0]
        normalized = _normalize_opt(option_token, self.ctx)
        if normalized in self._long_opt or normalized in self._short_opt:
            return True

        if arg_text.startswith("-") and not arg_text.startswith("--") and len(arg_text) > 2:
            prefix = arg_text[0]
            for ch in arg_text[1:]:
                short_opt = _normalize_opt(f"{prefix}{ch}", self.ctx)
                if short_opt in self._short_opt:
                    return True

        return False

    def _subcommand_index(self, args: list[str]) -> int | None:
        command = self.ctx.command
        if not isinstance(command, click.Group):
            return None

        required_values = 0
        for argument in self._args:
            parameter = argument.obj
            if not parameter.required:
                continue

            required_values += max(parameter.nargs, 1)

        for index, value in enumerate(args):
            if index < required_values:
                continue
            if command.get_command(self.ctx, value) is not None:
                return index

        return None

    def _process_args_for_args(self, state: ParsingStateLike) -> None:
        args = [*state.largs, *state.rargs]
        subcommand_index = self._subcommand_index(args)
        if subcommand_index is None:
            super()._process_args_for_args(state)
            return

        subcommand_args = args[subcommand_index:]
        state.largs = args[:subcommand_index]
        state.rargs = []
        super()._process_args_for_args(state)
        state.largs.extend(subcommand_args)

    def _get_value_from_state(
        self,
        option_name: str,
        option: OptionLike,
        state: ParsingStateLike,
    ) -> Any:
        if option.nargs != -1:
            return super()._get_value_from_state(option_name, option, state)

        collected: list[str] = []
        while state.rargs:
            next_rarg = state.rargs[0]
            if next_rarg == "--":
                state.rargs.pop(0)
                collected.extend(state.rargs)
                state.rargs.clear()
                break

            if self._token_looks_like_option(next_rarg):
                break

            collected.append(state.rargs.pop(0))

        return tuple(collected)


__all__ = ["InterfacyOptionParser"]

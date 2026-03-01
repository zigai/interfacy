from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, cast

import click.parser as click_parser


class _OptionLike(Protocol):
    nargs: int


class _ParsingStateLike(Protocol):
    rargs: list[str]


def _click_parser_symbol(name: str) -> object:
    """Load a click.parser symbol by name without direct private-member access."""
    try:
        return vars(click_parser)[name]
    except KeyError as exc:  # pragma: no cover - Click internals unexpectedly changed
        raise RuntimeError(f"Unsupported Click parser internals: missing {name!r}.") from exc


_BaseOptionParser: type[Any] = cast(type[Any], _click_parser_symbol("_OptionParser"))
_normalize_opt: Callable[[str, object], str] = cast(
    Callable[[str, object], str], _click_parser_symbol("_normalize_opt")
)


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

    def _get_value_from_state(
        self,
        option_name: str,
        option: _OptionLike,
        state: _ParsingStateLike,
    ) -> object:
        if getattr(option, "nargs", 1) != -1:
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

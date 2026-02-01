from __future__ import annotations

from typing import Any

import click.parser as click_parser

try:
    _BaseOptionParser = click_parser._OptionParser  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover - fallback for older/newer Click
    try:  # pragma: no cover
        from click import optparse as click_optparse  # type: ignore[import-not-found]

        _BaseOptionParser = click_optparse.OptionParser  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover
        _BaseOptionParser = click_parser.OptionParser  # type: ignore[assignment]


class InterfacyOptionParser(_BaseOptionParser):
    def _token_looks_like_option(self, token: str) -> bool:
        if token == "--":
            return True
        if not token or token[:1] not in self._opt_prefixes or len(token) == 1:
            return False

        option_token = token.split("=", 1)[0]
        normalized = click_parser._normalize_opt(option_token, self.ctx)
        if normalized in self._long_opt or normalized in self._short_opt:
            return True

        if token.startswith("-") and not token.startswith("--") and len(token) > 2:
            prefix = token[0]
            for ch in token[1:]:
                short_opt = click_parser._normalize_opt(f"{prefix}{ch}", self.ctx)
                if short_opt in self._short_opt:
                    return True
        return False

    def _get_value_from_state(self, option_name: str, option: Any, state: Any) -> Any:
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

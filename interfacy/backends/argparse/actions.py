from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Any

from interfacy.backends.base import ExecutableFlagTriggeredError
from interfacy.declarations.executable_flags import ExecutableFlag
from interfacy.exceptions import ConfigurationError


class ExecutableFlagAction(argparse.Action):
    """Argparse action that interrupts parsing when an executable flag is given."""

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        **kwargs: Any,
    ) -> None:
        flag = kwargs.pop("executable_flag")
        if not isinstance(flag, ExecutableFlag):
            raise ConfigurationError("Executable flag action requires ExecutableFlag")

        self.flag = flag
        super().__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: str | None = None,
    ) -> None:
        del parser, namespace, values, option_string
        raise ExecutableFlagTriggeredError(self.flag)


class BooleanAction(argparse.Action):
    """Argparse action storing True for positive flags and False for negative flags."""

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        default: Any = None,
        **kwargs: Any,
    ) -> None:
        self.positive = frozenset(kwargs.pop("positive_options"))
        super().__init__(option_strings, dest, nargs=0, default=default, **kwargs)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: str | None = None,
    ) -> None:
        del parser, values
        setattr(namespace, self.dest, option_string in self.positive)


__all__ = ["BooleanAction", "ExecutableFlagAction"]

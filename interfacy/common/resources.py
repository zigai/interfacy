from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import ExitStack
from types import TracebackType
from typing import Literal

from typing_extensions import Self

from interfacy.common.debug import get_logger

logger = get_logger(__name__)


class ResourceStack:
    def __init__(self) -> None:
        self._stack = ExitStack()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        try:
            self._stack.__exit__(exc_type, exc, traceback)
        except BaseException as e:
            if exc is None:
                raise

            logger.warning("Resource cleanup failed (%s)", type(e).__name__)

        return False

    def callback(self, close: Callable[[], None]) -> None:
        self._stack.callback(close)

    def pop_all(self) -> ResourceStack:
        resources = ResourceStack()
        resources._stack = self._stack.pop_all()
        return resources

    def close(self) -> None:
        self._stack.close()


class ParsedArguments(dict[str, object]):
    def __init__(self, values: Mapping[str, object], resources: ResourceStack) -> None:
        super().__init__(values)
        self._resources = resources

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        return self._resources.__exit__(exc_type, exc, traceback)

    def close(self) -> None:
        self._resources.close()


__all__ = ["ParsedArguments", "ResourceStack"]

from typing import Any

try:
    from interfacy.click_backend.core import ClickParser
except ImportError as exc:
    cause = getattr(exc, "__cause__", None)
    if not isinstance(cause, ModuleNotFoundError) or cause.name != "click":
        raise

    _CLICK_IMPORT_ERROR = exc

    class ClickParser:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError(
                "Click is required to use ClickParser. Install it with "
                "\"pip install 'interfacy[click]'\" or \"uv add 'interfacy[click]'\"."
            ) from _CLICK_IMPORT_ERROR


__all__ = ["ClickParser"]

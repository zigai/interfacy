from __future__ import annotations

from interfacy.backends.base import BackendAdapter
from interfacy.declarations.settings import BACKEND_NAMES, BackendName
from interfacy.exceptions import ConfigurationError


def create_backend_adapter(backend: BackendName) -> BackendAdapter[object]:
    if backend == "argparse":
        from interfacy.backends.argparse.adapter import ArgparseBackend

        return ArgparseBackend()

    if backend != "click":
        raise ConfigurationError(f"backend must be one of: {', '.join(BACKEND_NAMES)}")

    try:
        from interfacy.backends.click.adapter import ClickBackend
    except ImportError as e:
        if not _is_missing_click(e):
            raise

        raise ImportError(
            "Click is required to use Interfacy with backend='click'. Install it with "
            "\"pip install 'interfacy[click]'\" or \"uv add 'interfacy[click]'\"."
        ) from e

    return ClickBackend()


def _is_missing_click(error: BaseException) -> bool:
    """Recognize an absent Click package through an import failure's visible chain."""
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))

        if isinstance(current, ModuleNotFoundError) and current.name == "click":
            return True

        current = (
            current.__cause__
            if current.__suppress_context__
            else current.__cause__ or current.__context__
        )

    return False


__all__ = ["create_backend_adapter"]

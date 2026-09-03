from __future__ import annotations

import strto
from strto import StrToTypeParser


def build_default_type_parser(
    from_file: bool = True,
    *,
    allow_class_init: bool = False,
) -> StrToTypeParser:
    """
    Build Interfacy's default ``StrToTypeParser``.

    This mirrors ``strto.get_parser()`` except that ``list`` is intentionally omitted because
    Interfacy handles list-like arguments itself.
    """
    parser = strto.get_parser(from_file=from_file, allow_class_init=allow_class_init)
    _ = parser.parsers.pop(list, None)
    return parser


__all__ = ["build_default_type_parser"]

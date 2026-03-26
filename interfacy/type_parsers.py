from __future__ import annotations

import array
import datetime
import decimal
import fractions
import pathlib
from collections import Counter, OrderedDict, deque

from strto import StrToTypeParser
from strto.parsers import (
    ArrayParser,
    BoolParser,
    Cast,
    DateParser,
    DatetimeParser,
    FloatParser,
    IntParser,
    IterableParser,
    MappingParser,
    RangeParser,
    SliceParser,
    TimedeltaParser,
    TimeParser,
)

DIRECTLY_CASTABLE_TYPES = (
    str,
    decimal.Decimal,
    fractions.Fraction,
    pathlib.Path,
    pathlib.PosixPath,
    pathlib.WindowsPath,
    pathlib.PureWindowsPath,
    pathlib.PurePosixPath,
    bytearray,
)

ITERABLE_TYPES = (
    frozenset,
    deque,
    set,
    tuple,
)

MAPPING_TYPES_CAST = (
    dict,
    OrderedDict,
    Counter,
)


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
    parser = StrToTypeParser(from_file=from_file, allow_class_init=allow_class_init)
    for typ in DIRECTLY_CASTABLE_TYPES:
        parser.add(typ, Cast(typ))
    for typ in MAPPING_TYPES_CAST:
        parser.add(typ, MappingParser(typ, from_file=from_file, mode="cast"))
    for typ in ITERABLE_TYPES:
        parser.add(typ, IterableParser(typ, from_file=from_file))

    parser.extend(
        {
            int: IntParser(),
            float: FloatParser(),
            bool: BoolParser(),
            range: RangeParser(),
            slice: SliceParser(),
            datetime.datetime: DatetimeParser(),
            datetime.date: DateParser(),
            datetime.time: TimeParser(),
            datetime.timedelta: TimedeltaParser(),
            array.array: ArrayParser(),
        }
    )
    return parser


__all__ = ["build_default_type_parser"]

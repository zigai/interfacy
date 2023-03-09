import datetime
import decimal
import enum
import fractions
import functools
import inspect
import pathlib
from collections import ChainMap, Counter, OrderedDict, defaultdict, deque
from typing import Any, Callable, Dict, Iterable, List, Mapping, Tuple

from objinspect.util import UnionParameter, type_args, type_origin

from interfacy_cli.constants import ALIAS_TYPE, UNION_TYPE
from interfacy_cli.converters import *
from interfacy_cli.exceptions import UnsupportedParamError
from interfacy_cli.util import cast_dict_to, cast_iter_to, parse_and_cast


class Parser:
    def __init__(self) -> None:
        self.parsers: dict[Any, Callable] = {}

    def __len__(self):
        return len(self.parsers)

    def __getitem__(self, t: Any):
        return self.get(t)

    def add_parser(self, t: Any, func: Callable):
        self.parsers[t] = func

    def extend(self, parsers: dict[Any, Callable]):
        self.parsers = self.parsers | parsers

    def get(self, t: Any):
        return self.parsers[t]

    @functools.lru_cache(maxsize=256)
    def is_supported(self, t):
        return True  # TODO

    def parse(self, value: str, t: Any) -> Any:
        if parser := self.parsers.get(t, None):
            return parser(value)
        if value is None:
            return None
        if t is None:
            raise ValueError("None is not a valid type")
        if type(t) in ALIAS_TYPE:
            return self._parse_alias(value, t)
        if type(t) in UNION_TYPE:
            return self._parse_union(value, t)
        return self._parse_special(value, t)

    def _parse_alias(self, value: str, t: Any):
        """eg. list[int]"""
        base_type = type_origin(t)
        sub_types = type_args(t)
        parsed_as_origin = self.parse(value, base_type)
        if isinstance(base_type, Iterable):
            return cast_iter_to(parsed_as_origin, sub_types[0])
        if isinstance(base_type, Mapping):
            return cast_dict_to(parsed_as_origin, sub_types[0], sub_types[1])
        return self.get(base_type)(value, sub_types[0])  # TEMP

    def _parse_union(self, value: str, t: Any):
        """eg. float | int"""
        param = UnionParameter.from_type(t)
        for i in param:
            try:
                return self.parse(value, i)
            except Exception as e:
                continue
        raise UnsupportedParamError(t)

    def _parse_special(self, value: str, t: Any):
        if inspect.isclass(t):
            if issubclass(t, enum.Enum):
                return to_enum_value(value, t)
            if type_origin(t) == Literal:
                return to_literal_value(value, t)
        raise UnsupportedParamError(t)


PARSER = Parser()
PARSER.extend(
    {
        datetime.datetime: to_datetime,
        datetime.date: to_date,
        set: to_set,
        tuple: to_tuple,
        range: to_range,
        slice: to_slice,
        list: to_list,
        dict: to_dict,
        Dict: to_dict,
        List: to_list,
        Tuple: to_tuple,
        list[dict]: to_mapping,  # TEMP
        bytes: to_bytes,
    }
)


# These types can be casted to directly from a string
DIRECTLY_CASTABLE_TYPES = [
    bool,
    str,
    int,
    float,
    decimal.Decimal,
    fractions.Fraction,
    pathlib.Path,
    pathlib.PosixPath,
    pathlib.WindowsPath,
    pathlib.PureWindowsPath,
    pathlib.PurePosixPath,
    bytearray,
]
MAPPING_CONTAINER_TYPES = [dict, OrderedDict, defaultdict, ChainMap, Counter]
ITER_CONTAINER_TYPES = [frozenset, deque]

for i in DIRECTLY_CASTABLE_TYPES:
    PARSER.add_parser(i, i)
for i in MAPPING_CONTAINER_TYPES:
    PARSER.add_parser(i, parse_and_cast(to_mapping, i))
for i in ITER_CONTAINER_TYPES:
    PARSER.add_parser(i, parse_and_cast(to_iter, i))

__all__ = ["PARSER"]

import datetime
import decimal
import enum
import fractions
import functools
import inspect
import json
import pathlib
from typing import *
from typing import Any, Callable, get_args, get_origin, get_type_hints

from py_inspect.util import UnionParameter, type_args, type_origin
from stdl import dt
from stdl.fs import File, json_load, pickle_load, yaml_load

from interfacy_cli.constants import ALIAS_TYPE, EMPTY, ITEM_SEP, SIMPLE_TYPES, UNION_TYPE
from interfacy_cli.exceptions import UnsupportedParamError
from interfacy_cli.util import cast_dict_to, cast_iter_to, cast_to, is_file, parse_then_cast

ITER_SEP = ","
RANGE_SEP = ":"
# These types can be casted to directly from a string
DIRECT_TYPES = [
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
]


class Parser:
    def __init__(self) -> None:
        # type[parser]
        self.parsers: dict[Any, Callable] = {
            datetime.datetime: to_datetime,
            datetime.date: to_date,
            set: to_set,
            tuple: to_tuple,
            range: to_range,
            slice: to_slice,
            list: to_list,
        }

        for i in DIRECT_TYPES:
            self.add_parser(i, cast_to)

    def add_parser(self, t: Any, func: Callable):
        self.parsers[t] = func

    def extend(self, parsers: dict[Any, Callable]):
        self.parsers = self.parsers | parsers

    def get_parser(self, t: Any):
        return self.parsers[t]

    @functools.lru_cache(maxsize=256)
    def is_supported(self, t):
        if t in SIMPLE_TYPES:
            return True
        if t is EMPTY:
            return True
        if t in self.parsers:
            return True

        if type(t) in ALIAS_TYPE:
            base = type_origin(t)
            sub = type_args(t)
            if self.is_supported(base):
                for i in sub:
                    if not self.is_supported(i):
                        return False
                return True
        if type(t) in UNION_TYPE:
            for i in UnionParameter.from_type(t):
                if self.is_supported(i):
                    return True
            return False

        if inspect.isclass(t):
            if issubclass(t, enum.Enum):
                return True
        return False

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
        t_origin = type_origin(t)
        t_sub = type_args(t)
        print(t_origin)
        print(t_sub)
        return self.get_parser(t_origin)(value, t_sub[0])
        if isinstance(
            t_origin,
        ):
            ...
        for i in t_sub:
            try:
                return t_origin(map(i, origin_parsed))
            except Exception as e:
                print(e)
        raise UnsupportedParamError(t)

    def _parse_union(self, value: str, t: Any):
        ...

    def _parse_special(self, value: str, t: Any):
        if inspect.isclass(value):
            if issubclass(t, enum.Enum):
                return to_enum_value(value, t)


def to_iter(value) -> Iterable:
    if isinstance(value, str):
        if is_file(value):
            data = File(value).splitlines()
            data = [i.strip() for i in data]
            if len(data) == 1 and ITER_SEP in data[0]:
                data = data[0].split(ITER_SEP)
            return [i.strip() for i in data]
        return [i.strip() for i in value.split(ITER_SEP)]
    if isinstance(value, Iterable):
        return list_split(value)
    raise TypeError(f"Cannot convert {value} to an iterable")


def list_split(value: list[str]) -> list[list]:
    return [i.split(ITER_SEP) for i in value]


def to_mapping(value) -> Mapping:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        if is_file(value):
            if value.endswith(("yaml", "yml")):
                return yaml_load(value)  # type:ignore
            return json_load(value)  # type:ignore
        return json.loads(value)
    raise TypeError(f"Cannot convert {value} to a mapping")


def to_enum_value(value: str, enum_cls: Type[enum.Enum]) -> enum.Enum:
    if type(value) is enum_cls:
        return value
    return enum_cls[value]


def to_datetime(value) -> datetime.datetime:
    if type(value) is datetime.datetime:
        return value
    return dt.parse_datetime_str(value)


def to_date(value) -> datetime.date:
    if type(value) is datetime.date:
        return value
    return dt.parse_datetime_str(value).date()


def to_tuple(value) -> tuple:
    if isinstance(value, tuple):
        return value
    return (*to_iter(value),)


def cast(value: Any, t: Any):
    if isinstance(value, t):
        return value
    return t(value)


def to_set(value, t=None) -> set:
    if isinstance(value, set):
        if t is None:
            return value
        return {cast(i, t) for i in value}
    vals = to_iter(value)
    if t is not None:
        vals = [cast(i, t) for i in vals]
    return cast(vals, set)


def to_list(value, t=None):
    if isinstance(value, list):
        if t is None:
            return value
        return [cast(i, t) for i in value]
    vals = to_iter(value)
    if t is not None:
        vals = [cast(i, t) for i in vals]
    return vals


def to_range(value) -> range:
    if isinstance(value, range):
        return value
    nums = value.split(RANGE_SEP)
    nums = [int(i) for i in nums]
    if not len(nums) == 3:
        raise ValueError(
            f"Too many values for range: {value}. Must be 1-3 values separated by {RANGE_SEP}"
        )
    return range(*nums)


def to_slice(value) -> slice:
    if isinstance(value, slice):
        return value
    nums = value.split(RANGE_SEP)
    nums = [int(i) for i in nums]
    if not len(nums) == 3:
        raise ValueError(
            f"Too many values for slice: {value}. Must be 1-3 values separated by {RANGE_SEP}"
        )
    return slice(*nums)


PARSER = Parser()

x = PARSER.parse("1,2,3,4,5", list[int])
print("x:", x)

x = PARSER.parse("1,2,3,4,5", set[int])
print("x:", x)

x = PARSER.parse("./nested_list.txt", list[list[int]])
print("x:", x)

__all__ = ["PARSER"]

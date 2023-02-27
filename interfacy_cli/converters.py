import datetime
import enum
import json
from typing import Iterable, Mapping, Type

from stdl import dt
from stdl.fs import File, json_load, yaml_load

from interfacy_cli.util import cast, is_file

ITER_SEP = ","
RANGE_SEP = ":"


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


def list_split(value: list | Iterable) -> list[list]:
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


def to_set(value, t=None) -> set:
    if isinstance(value, set):
        if t is None:
            return value
        return {cast(i, t) for i in value}
    vals = to_iter(value)
    if t is not None:
        vals = [cast(i, t) for i in vals]
    return cast(vals, set)


def to_list(value, t=None) -> list:
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
    if not len(nums) in (1, 2, 3):
        raise ValueError(f"Range arg must be 1-3 values separated by {RANGE_SEP}")
    return range(*nums)


def to_slice(value) -> slice:
    if isinstance(value, slice):
        return value
    nums = value.split(RANGE_SEP)
    nums = [float(i) for i in nums]
    if not len(nums) in (1, 2, 3):
        raise ValueError(f"Slice arg must be 1-3 values separated by {RANGE_SEP}")
    return slice(*nums)


def to_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    return dict(**to_mapping(value))

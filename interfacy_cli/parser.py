import datetime
import decimal
import enum
import fractions
import functools
import inspect
import json
import pathlib
from typing import Any, Callable, get_args, get_origin, get_type_hints

from py_inspect.util import type_args, type_origin
from stdl import datetime_u
from stdl.fs import File, json_load, pickle_load, yaml_load

from interfacy_cli.constants import ALIAS_TYPE, EMPTY, ITEM_SEP, SIMPLE_TYPE, UNION_TYPE
from interfacy_cli.exceptions import UnsupportedParamError
from interfacy_cli.util import (
    cast_dict_to,
    cast_iter_to,
    cast_to,
    is_file,
    parse_then_cast,
)


class Parser:
    def __init__(self) -> None:
        self.parsers = {
            # These types can be casted to from a string
            str: str,
            int: int,
            float: float,
            decimal.Decimal: decimal.Decimal,
            fractions.Fraction: fractions.Fraction,
            pathlib.Path: pathlib.Path,
            pathlib.PosixPath: pathlib.PosixPath,
            pathlib.WindowsPath: pathlib.WindowsPath,
            pathlib.PureWindowsPath: pathlib.PureWindowsPath,
            pathlib.PurePosixPath: pathlib.PurePosixPath,
            datetime.date: parse_date,
            datetime.datetime: parse_datetime,
            # ---
            dict: parse_dict,
            list: parse_list,
            set: parse_set,
            tuple: parse_tuple,
            list[dict]: parse_dict,
        }

    @functools.lru_cache(maxsize=128)
    def is_supported(self, t):
        if t in SIMPLE_TYPE:
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
            return False
        if inspect.isclass(t):
            if issubclass(t, enum.Enum):
                return True
        return False

    def add_parser(self, t, func: Callable):
        self.parsers[t] = func

    def extend(self, parsers: dict[Any, Callable]):
        self.parsers = self.parsers | parsers

    def get_parser(self, t):
        return self.parsers[t]

    def parse(self, val: str, t) -> Any:
        if t in self.parsers:
            return self.parsers[t](val)
        if type(t) in ALIAS_TYPE:
            base_type = get_origin(t)
            subtype = get_args(t)
            as_base = self.parse(val, base_type)
            for i in subtype:
                try:
                    return base_type(map(i, as_base))
                except Exception as e:
                    print(e)
            raise UnsupportedParamError(t)
        print(val)
        print(type(val))
        if inspect.isclass(val):
            if issubclass(t, enum.Enum):
                return parse_enum(val, t)


def parse_datetime(val) -> datetime.datetime:
    if type(val) is datetime.datetime:
        return val
    return datetime_u.parse_datetime(val)


def parse_date(val) -> datetime.date:
    if type(val) is datetime.date:
        return val
    return datetime_u.parse_datetime(val).date()


def parse_list(val: str):
    if isinstance(val, list):
        return val
    return split_iter_arg(val)


def parse_dict(val: str) -> dict:
    if type(val) is dict:
        return val
    # JSON string needs to be enclosed in single quotes
    if is_file(val):
        if val.endswith(("yaml", "yml")):
            return yaml_load(val)
        return json_load(val)
    return json.loads(val)


def split_iter_arg(val: str):
    if is_file(val):
        file_data = File(val).splitlines()
        file_data = [i.strip() for i in file_data]
        if len(file_data) == 1 and ITEM_SEP in file_data[0]:
            file_data = file_data[0].split(ITEM_SEP)
        return [i.strip() for i in file_data]
    data = val.split(ITEM_SEP)
    return [i.strip() for i in data]


def parse_set(val) -> set:
    if type(val) is set:
        return val
    return set(split_iter_arg(val))


def parse_tuple(val):
    if type(val) is tuple:
        return val
    return (*split_type_hint(val),)


def parse_enum(val: str, t):
    if type(val) is t:
        return val
    return t[val]


PARSER = Parser()


__all__ = ["PARSER"]

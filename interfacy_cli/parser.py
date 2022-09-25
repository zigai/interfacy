import datetime
import decimal
import fractions
import json
import pathlib
from typing import Any, Callable, get_args, get_origin, get_type_hints

from interfacy_core.constants import ALIAS_TYPE, UNION_TYPE
from interfacy_core.exceptions import UnsupportedParamError
from interfacy_core.util import UnionTypeParameter, is_file
from stdl.datetime_u import parse_datetime as dt_parse
from stdl.fs import File, json_load, pickle_load, yaml_load

from interfacy_cli.constants import ITEM_SEP
from interfacy_cli.util import cast_dict_to, cast_iter_to, cast_to, parse_then_cast


class Parser:
    def __init__(self) -> None:
        self.parsers = {
            # These types can be casted to from a string
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
            list[dict]: parse_dict,
        }

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
            orig = get_origin(t)
            args = get_args(t)
            ls = self.parse(val, list)
            for i in args:
                try:
                    return orig(map(i, ls))
                except Exception as e:
                    print(e)


def parse_datetime(val) -> datetime.datetime:
    if type(val) is datetime.datetime:
        return val
    return dt_parse(val)


def parse_date(val) -> datetime.date:
    if type(val) is datetime.date:
        return val
    return dt_parse(val).date()


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


PARSER = Parser()


# -----
def tuple_arg(val) -> tuple:
    if type(val) is tuple:
        return val
    if is_file(val):
        return (*File(val).splitlines(),)
    return (*val.split(ITEM_SEP),)


__all__ = ["PARSER"]

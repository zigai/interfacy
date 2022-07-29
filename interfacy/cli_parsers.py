import datetime
import decimal
import enum
import fractions
import json
import pathlib

from stdl.datetime_util import parse_datetime
from stdl.fs import File, json_load, pickle_load, yaml_load

from interfacy.interfacy_parameter import UnionTypeParameter
from interfacy.util import (cast_dict_to, cast_iter_to, cast_to, is_file, parse_and_cast)

SEP = ","


def datetime_arg(val) -> datetime.datetime:
    return parse_datetime(val)


def date_arg(val) -> datetime.date:
    return parse_datetime(val).date()


def dict_arg(val) -> dict:
    # JSON string needs to be enclosed in single quotes
    if is_file(val):
        if val.endswith(("yaml", "yml")):
            return yaml_load(val)
        return json_load(val)
    return json.loads(val)


def list_arg(val) -> list:
    if is_file(val):
        data = File(val).splitlines()
        # if all data is in a single line
        if len(data) == 1 and SEP in data[0]:
            data = data[0].split(SEP)
        return data
    return val.split(SEP)


def set_arg(val) -> set:
    if is_file(val):
        return set(File(val).splitlines())
    return set(val.split(SEP))


def tuple_arg(val) -> tuple:
    if is_file(val):
        return (*File(val).splitlines(),)
    return (*val.split(SEP),)


CLI_PARSER = {
    dict: dict_arg,
    list: list_arg,
    set: set_arg,
    tuple: tuple_arg,
    datetime.date: date_arg,
    datetime.datetime: datetime_arg,
    #
    float: cast_to(float),
    decimal.Decimal: cast_to(decimal.Decimal),
    fractions.Fraction: cast_to(fractions.Fraction),
    pathlib.Path: cast_to(pathlib.Path),
    pathlib.PosixPath: cast_to(pathlib.PosixPath),
    pathlib.WindowsPath: cast_to(pathlib.WindowsPath),
    pathlib.PureWindowsPath: cast_to(pathlib.PureWindowsPath),
    pathlib.PurePosixPath: cast_to(pathlib.PurePosixPath),
    #
    list[int]: parse_and_cast(list_arg, cast_iter_to(list, int)),
    list[float]: parse_and_cast(list_arg, cast_iter_to(list, float)),
    list[decimal.Decimal]: parse_and_cast(list_arg, cast_iter_to(list, decimal.Decimal)),
    list[fractions.Fraction]: parse_and_cast(list_arg, cast_iter_to(list, fractions.Fraction)),
}

import datetime
import decimal
import fractions
import json
import pathlib

from interfacy_cli.interfacy_parameter import UnionTypeParameter
from interfacy_cli.util import (cast_dict_to, cast_iter_to, cast_to,
                                parse_then_cast)
from stdl.datetime_util import parse_datetime
from stdl.fs import File, json_load, pickle_load, yaml_load

SEP = ","


def datetime_arg(val) -> datetime.datetime:
    if type(val) is datetime.datetime:
        return val
    return parse_datetime(val)


def date_arg(val) -> datetime.date:
    if type(val) is datetime.date:
        return val
    return parse_datetime(val).date()


def dict_arg(val) -> dict:
    if type(val) is dict:
        return val
    # JSON string needs to be enclosed in single quotes
    if File(val).exists:
        if val.endswith(("yaml", "yml")):
            return yaml_load(val)
        return json_load(val)
    return json.loads(val)


def list_arg(val) -> list:
    if type(val) is list:
        return val
    if is_file(val):
        data = File(val).splitlines()
        # if all data is in a single line
        if len(data) == 1 and SEP in data[0]:
            data = data[0].split(SEP)
        return data
    return val.split(SEP)


def set_arg(val) -> set:
    if type(val) is set:
        return val
    if is_file(val):
        return set(File(val).splitlines())
    return set(val.split(SEP))


def tuple_arg(val) -> tuple:
    if type(val) is tuple:
        return val
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
    # These types can be casted to from a string
    float: cast_to(float),
    decimal.Decimal: cast_to(decimal.Decimal),
    fractions.Fraction: cast_to(fractions.Fraction),
    pathlib.Path: cast_to(pathlib.Path),
    pathlib.PosixPath: cast_to(pathlib.PosixPath),
    pathlib.WindowsPath: cast_to(pathlib.WindowsPath),
    pathlib.PureWindowsPath: cast_to(pathlib.PureWindowsPath),
    pathlib.PurePosixPath: cast_to(pathlib.PurePosixPath),
    #
    list[int]: parse_then_cast(list_arg, cast_iter_to(list, int)),
    list[float]: parse_then_cast(list_arg, cast_iter_to(list, float)),
    list[decimal.Decimal]: parse_then_cast(list_arg, cast_iter_to(list, decimal.Decimal)),
    list[fractions.Fraction]: parse_then_cast(list_arg, cast_iter_to(list, fractions.Fraction)),
}

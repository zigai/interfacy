import datetime
import json
import pathlib

from dateutil import parser as date_parser
from stdl.fs import File, json_load, pickle_load, yaml_load

from interfacy.util import is_file

SEP = ","


def date_arg(arg: str):
    return date_parser.parse(arg)


def dict_arg(arg: str):
    if is_file(arg):
        if arg.endswith(("yaml", "yml")):
            return yaml_load(arg)
        return json_load(arg)
    return json.loads(arg)


def list_arg(arg: str):
    if is_file(arg):
        data = File.splitlines(arg)
        # if all data is in a single line
        if len(data) == 1 and SEP in data[0]:
            data = data[0].split(SEP)
        return data
    return arg.split(SEP)


def set_arg(arg: str):
    if is_file(arg):
        return set(File.splitlines(arg))
    return set(arg.split(SEP))


def tuple_arg(arg: str):
    if is_file(arg):
        return (*File.splitlines(arg),)
    return (*File.splitlines(arg),)


def path_arg(arg):
    return pathlib.Path(arg)


def posix_path_arg(arg: str):
    return pathlib.PosixPath(arg)


def pure_windows_path_arg(arg: str):
    return pathlib.PureWindowsPath(arg)


def windows_path_arg(arg: str):
    return pathlib.WindowsPath(arg)


def pure_posix_path_arg(arg: str):
    return pathlib.PurePosixPath(arg)


CLI_TYPE_PARSER = {
    dict: dict_arg,
    list: list_arg,
    set: set_arg,
    tuple: tuple_arg,
    datetime.date: date_arg,
    datetime.datetime: date_arg,
    pathlib.Path: path_arg,
    pathlib.PosixPath: posix_path_arg,
    pathlib.WindowsPath: windows_path_arg,
    pathlib.PureWindowsPath: pure_windows_path_arg,
    pathlib.PurePosixPath: pure_posix_path_arg,
}

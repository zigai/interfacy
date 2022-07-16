import datetime
import json
import pathlib

from dateutil import parser as date_parser
from stdl.fs import File, json_load, pickle_load, yaml_load

from util import is_file

SEP = ","


def parse_date(arg: str):
    return date_parser.parse(arg)


def parse_dict(arg: str):
    if is_file(arg):
        if arg.endswith(("yaml", "yml")):
            return yaml_load(arg)
        return json_load(arg)
    return json.loads(arg)


def parse_list(arg: str):
    if is_file(arg):
        return File.splitlines(arg)
    return arg.split(SEP)


def parse_set(arg: str):
    if is_file(arg):
        return set(File.splitlines(arg))
    return set(arg.split(SEP))


def parse_tuple(arg: str):
    if is_file(arg):
        return (*File.splitlines(arg),)
    return (*File.splitlines(arg),)


def parse_path(arg):
    return pathlib.Path(arg)


CLI_TYPE_PARSER = {
    dict: parse_dict,
    list: parse_list,
    set: parse_set,
    tuple: parse_tuple,
    datetime.date: parse_date,
    datetime.datetime: parse_date,
    pathlib.Path: parse_path
}

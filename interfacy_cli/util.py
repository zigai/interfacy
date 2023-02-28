import os
import sys
from typing import Any, Callable, Iterable, Mapping

from stdl.fs import File, assert_paths_exist, json_dump, json_load, yaml_load


def is_file(path: str) -> bool:
    return os.path.isfile(path)


def cast_to(t):
    """
    Returns a functions that casts a string to type 't'
    """

    def inner(arg: str) -> t:
        if isinstance(arg, t):
            return arg
        return t(arg)

    return inner


def cast(value: Any, t: Any):
    if isinstance(value, t):
        return value
    return t(value)


def cast_iter_to(iterable: Iterable, t: Any):
    def inner(arg) -> iterable[t]:
        l = [t(i) for i in arg]
        return iterable(l)

    return inner


def cast_dict_to(k: Any, v: Any):
    def inner(arg: dict) -> dict[k, v]:
        return {k(key): v(val) for key, val in arg.items()}

    return inner


def parse_and_cast(parser: Callable, caster: Any):
    def inner(val):
        if isinstance(val, caster):
            return val
        return caster(parser(val))

    return inner


def args_from_file(path: str) -> list[str]:
    """
    Get arguments from a file.
    """

    def dict_extract(d: dict):
        args = []
        for k, v in d.items():
            args.append(k)
            args.append(v)
        return args

    assert_paths_exist(path)
    if path.endswith(".json"):
        return dict_extract(json_load(path))
    if path.endswith(".yaml"):
        return dict_extract(yaml_load(path))
    args = []
    for line in File(path).splitlines():
        line = line.strip().split(" ")
        arg_name = line[0]
        arg_val = " ".join(line[1:])
        args.append(arg_name)
        args.append(arg_val)
    return args


def get_args(args: list[str] | None, from_file_prefix="@F") -> list[str]:
    args = args or sys.argv
    parsed_args = []
    i = 1
    while i < len(args):
        print(sys.argv[i])
        if args[i] == from_file_prefix:
            i += 1
            parsed_args.extend(args_from_file(args[i]))
        else:
            parsed_args.append(args[i])
        i += 1
    return parsed_args


def get_command_abbrev(name: str, taken: list[str]) -> str | None:
    """
    Tries to return a short name for a command.
    Returns None if it cannot find a short name.

    Example:
        >>> get_command_short_name("hello_world", [])
        >>> "h"
        >>> get_command_short_name("hello_world", ["h"])
        >>> "hw"
        >>> get_command_short_name("hello_world", ["hw", "h"])
        >>> "he"
        >>> get_command_short_name("hello_world", ["hw", "h", "he"])
        >>> None
    """
    if name in taken:
        raise ValueError(f"Command name '{name}' already taken")
    if len(name) < 3:
        return name
    name_split = name.split("_")
    if name_split[0][0] not in taken:
        taken.append(name_split[0][0])
        return name_split[0][0]
    short_name = "".join([i[0] for i in name_split])
    if short_name not in taken:
        taken.append(short_name)
        return short_name
    try:
        short_name = name_split[0][:2]
        if short_name not in taken:
            taken.append(short_name)
            return short_name
        return None
    except IndexError:
        return None

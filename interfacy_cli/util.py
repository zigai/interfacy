import sys
from argparse import ArgumentParser
from typing import Callable

from stdl.fs import File, assert_paths_exist, json_load, yaml_load


def read_args_from_file(path: str) -> list[str]:
    """
    Get arguments from a file.
    """
    assert_paths_exist(path)

    def dict_extract(d: dict):
        args = []
        for k, v in d.items():
            args.append(k)
            args.append(v)
        return args

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


def get_args(args: list[str] | None = None, from_file_prefix="@F") -> list[str]:
    args = args or sys.argv
    parsed_args = []
    i = 1
    while i < len(args):
        if args[i] == from_file_prefix:
            i += 1
            parsed_args.extend(read_args_from_file(args[i]))
        else:
            parsed_args.append(args[i])
        i += 1
    return parsed_args


def get_abbrevation(name: str, taken: list[str]) -> str | None:
    """
    Tries to return a short name for a command.
    Returns None if it cannot find a short name.

    Example:
        >>> get_abbrevation("hello_world", [])
        >>> "h"
        >>> get_abbrevation("hello_world", ["h"])
        >>> "hw"
        >>> get_abbrevation("hello_world", ["hw", "h"])
        >>> "he"
        >>> get_abbrevation("hello_world", ["hw", "h", "he"])
        >>> None
    """
    if name in taken:
        raise ValueError(f"Command name '{name}' already taken")
    if len(name) < 3:
        return None
    name_split = name.split("_")
    abbrev = name_split[0][0]
    if abbrev not in taken and abbrev != name:
        taken.append(abbrev)
        return abbrev
    short_name = "".join([i[0] for i in name_split])
    if short_name not in taken and short_name != name:
        taken.append(short_name)
        return short_name
    try:
        short_name = name_split[0][:2]
        if short_name not in taken and short_name != name:
            taken.append(short_name)
            return short_name
        return None
    except IndexError:
        return None


def simplify_type(t: str) -> str:
    t = t.split(".")[-1]
    t = t.replace("| None", "").strip()
    return t


def install_tab_completion(parser: ArgumentParser) -> None:
    """Install tab completion for the given parser"""
    try:
        import argcomplete

    except ImportError:
        print(
            "argcomplete not installed. Tab completion not available."
            " Install with 'pip install argcomplete'",
            file=sys.stderr,
        )
        return

    argcomplete.autocomplete(parser)


class Translator:
    def __init__(self, translate_func: Callable) -> None:
        self.translate_func = translate_func
        self.translations: dict[str, str] = {}

    def translate(self, name: str, mode: str):
        translated_name = self.translate_func(name)
        self.translations[translated_name] = name
        return translated_name

    def get_original(self, translated_name: str) -> str:
        if original := self.translations.get(translated_name):
            return original
        return translated_name

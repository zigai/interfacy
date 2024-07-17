import sys
from argparse import ArgumentParser
from typing import Callable

from stdl.fs import File, ensure_paths_exist, json_load, yaml_load


def read_args_from_file(path: str) -> list[str]:
    """
    Get arguments from a file.
    """
    ensure_paths_exist(path)

    def extract_args(d: dict):
        args = []
        for k, v in d.items():
            args.append(k)
            args.append(v)
        return args

    if path.endswith(".json"):
        return extract_args(json_load(path))  # type:ignore
    if path.endswith(".yaml"):
        return extract_args(yaml_load(path))  # type:ignore

    args = []
    for line in File(path).splitlines():
        line = line.strip().split(" ")
        arg_name = line[0]
        arg_value = " ".join(line[1:])
        args.append(arg_name)
        args.append(arg_value)
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


def get_abbrevation(value: str, taken: list[str], min_len: int = 3) -> str | None:
    """
    Tries to return a short name for a command.
    Returns None if it cannot find a short name.

    Args:
        value (str): The value to abbreviate.
        taken (list[str]): List of taken abbreviations.
        min_len (int, optional): Minimum length of the value to abbreviate. Defaults to 3.
            If the value is shorter than this, None will be returned.

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
    if value in taken:
        raise ValueError(f"Command name '{value}' already taken")

    if len(value) < min_len:
        return None

    name_split = value.split("_")
    abbrev = name_split[0][0]
    if abbrev not in taken and abbrev != value:
        taken.append(abbrev)
        return abbrev

    short_name = "".join([i[0] for i in name_split])
    if short_name not in taken and short_name != value:
        taken.append(short_name)
        return short_name
    try:
        short_name = name_split[0][:2]
        if short_name not in taken and short_name != value:
            taken.append(short_name)
            return short_name
        return None
    except IndexError:
        return None


def simplified_type_name(name: str) -> str:
    """
    Simplifies the type name by removing module paths and optional "None" union.
    """
    name = name.split(".")[-1]
    name = name.replace("| None", "").strip()
    return name


class Translator:
    """
    Handles translation of strings through a provided function and keeps a record of translations.

    Attributes:
        translation_func (Callable): Function to translate a string.
        translations (dict[str, str]): Dictionary to store translated names and their originals.

    """

    def __init__(self, translation_func: Callable) -> None:
        """
        Initialize the Translator instance.

        Args:
            translate_func (Callable): Function to use for translating strings.
        """
        self.translation_func = translation_func
        self.translations: dict[str, str] = {}

    def get_translation(self, name: str) -> str:
        """
        Translate a string and save the translation.

        Args:
            name (str): The original name to be translated.

        Returns:
            str: The translated name.
        """
        translated_name = self.translation_func(name)
        self.translations[translated_name] = name
        return translated_name

    def get_original(self, translated: str) -> str:
        """
        Retrieve the original name based on the translated name.

        Args:
            translated (str): The translated name whose original name needs to be found.

        Returns:
            str: The original name if it exists, otherwise returns the same translated name.
        """
        if original := self.translations.get(translated):
            return original
        return translated

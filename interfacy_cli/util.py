import typing as T
from typing import Callable

from objinspect.typing import type_origin


def simplified_type_name(name: str) -> str:
    """
    Simplifies the type name by removing module paths and optional "None" union.
    """
    name = name.split(".")[-1]
    name = name.replace("| None", "").strip()
    return name


def is_list_or_list_alias(t):
    if t is list:
        return True
    t_origin = type_origin(t)
    return t_origin is list


def show_result(result: T.Any, handler=print):
    if isinstance(result, list):
        for i in result:
            handler(i)
    elif isinstance(result, dict):
        from pprint import pprint

        pprint(result)
    else:
        handler(result)


def inverted_bool_flag_name(name: str) -> str:
    return "no-" + name


class TranslationMapper:
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
        self.ignored_names: set[str] = set()

    def add_ignored(self, name: str):
        self.ignored_names.add(name)

    def translate(self, name: str) -> str:
        """
        Translate a string and save the translation.

        Args:
            name (str): The original name to be translated.

        Returns:
            str: The translated name.
        """
        if name in self.ignored_names:
            return name
        translated_name = self.translation_func(name)
        self.translations[translated_name] = name
        return translated_name

    def reverse(self, translated: str) -> str | None:
        """
        Retrieve the original name based on the translated name.

        Args:
            translated (str): The translated name whose original name needs to be found.

        Returns:
            str: The original name if it exists, otherwise returns the same translated name.
        """
        if translated in self.ignored_names:
            return translated
        return self.translations.get(translated, None)

    def contains_key(self, name: str):
        return name in self.translations.values()

    def contains_translation(self, name: str):
        return name in self.translations


class AbbrevationGenerator:
    def generate(self, value: str, taken: list[str]) -> str | None: ...


class DefaultAbbrevationGenerator(AbbrevationGenerator):
    """
    Simple abbrevation generator that tries to return a short name for a command.
    Returns None if it cannot find a short name.

        Args:
        taken (list[str]): List of taken abbreviations.
        min_len (int, optional): Minimum length of the value to abbreviate. If the value is shorter than this, None will be returned.

    Example:
        >>> AbbrevationGenerator(taken=[]).generate("hello_word")
        "h"
        >>> AbbrevationGenerator(taken=["h"]).generate("hello_word")
        "hw"
        >>> AbbrevationGenerator(taken=["hw", "h"]).generate("hello_word")
        "he"
        >>> AbbrevationGenerator(taken=["hw", "h", "he"]).generate("hello_word")
        None

    """

    def __init__(self, min_len: int = 3) -> None:
        self.min_len = min_len

    def generate(self, value: str, taken: list[str]) -> str | None:
        if value in taken:
            raise ValueError(f"'{value}' is already an abbervation")

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


class NoAbbrevations(AbbrevationGenerator):
    def generate(self, value: str, taken: list[str]) -> str | None:
        return None


def revese_arg_translations(args: dict, arg_translator: TranslationMapper) -> dict[str, T.Any]:
    reversed = {}
    for k, v in args.items():
        k = arg_translator.reverse(k)
        reversed[k] = v
    return reversed


__all__ = [
    "simplified_type_name",
    "AbbrevationGenerator",
    "DefaultAbbrevationGenerator",
    "NoAbbrevations",
    "TranslationMapper",
    "is_list_or_list_alias",
    "show_result",
    "inverted_bool_flag_name",
    "revese_arg_translations",
]

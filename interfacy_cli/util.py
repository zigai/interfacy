import sys
from argparse import ArgumentParser
from typing import Callable

from stdl.fs import File, ensure_paths_exist, json_load, yaml_load

def simplified_type_name(name: str) -> str:
    """
    Simplifies the type name by removing module paths and optional "None" union.
    """
    name = name.split(".")[-1]
    name = name.replace("| None", "").strip()
    return name

class AbbrevationGeneratorProtocol:
    def generate(self, value: str) -> str | None: ...


class AbbrevationGenerator(AbbrevationGeneratorProtocol):
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
    def __init__(self, taken: list[str] | None = None, min_len: int = 3) -> None:
        self.min_len = min_len
        self.taken = taken or []

    def generate(self, value: str) -> str | None:
        if value in self.taken:
            raise ValueError(f"'{value}' is already an abbervation")

        name_split = value.split("_")
        abbrev = name_split[0][0]
        if abbrev not in self.taken and abbrev != value:
            self.taken.append(abbrev)
            return abbrev
        short_name = "".join([i[0] for i in name_split])
        if short_name not in self.taken and short_name != value:
            self.taken.append(short_name)
            return short_name
        try:
            short_name = name_split[0][:2]
            if short_name not in self.taken and short_name != value:
                self.taken.append(short_name)
                return short_name
            return None
        except IndexError:
            return None


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

    def translate(self, name: str) -> str:
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

    def reverse(self, translated: str) -> str | None:
        """
        Retrieve the original name based on the translated name.

        Args:
            translated (str): The translated name whose original name needs to be found.

        Returns:
            str: The original name if it exists, otherwise returns the same translated name.
        """
        return self.translations.get(translated,None):

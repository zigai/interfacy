from collections.abc import Callable
from typing import Any


class MappingCache:
    """
    Handles translation of strings through a provided function and keeps a record of translations.

    Attributes:
        translations (dict[str, str]): Dictionary to store translated names and their originals.
    """

    def __init__(
        self, translation_fn: Callable[[str], str], ignored: set[str] | None = None
    ) -> None:
        """
        Args:
            translation_fn (Callable): Function to use for translating strings.
            ignored (set[str], optional): Set of names to ignore during translation. Defaults to None.
        """
        self.translation_fn = translation_fn
        self.ignored_names: set[str] = ignored if ignored is not None else set()
        self.translations: dict[str, str] = {}

    def add_ignored(self, name: str):
        self.ignored_names.add(name)

    def translate(self, key: str) -> str:
        """
        Translate a string and save the translation.

        Args:
            key (str): The original name to be translated.

        Returns:
            str: The translated name.
        """
        if key in self.ignored_names:
            return key
        translated_key = self.translation_fn(key)
        self.translations[translated_key] = key
        return translated_key

    def reverse(self, translated: str) -> str:
        """
        Retrieve the original name based on the translated name. If the translated name is not found, it is returned as is.

        Args:
            translated (str): The translated name whose original name needs to be found.

        Returns:
            str: The original name if it exists, otherwise returns the same translated name.
        """
        if translated in self.ignored_names:
            return translated
        return self.translations.get(translated, translated)

    def contains_key(self, name: str) -> bool:
        return name in self.translations.values()

    def contains_translation(self, name: str) -> bool:
        return name in self.translations


def revese_translations(args: dict[str, str], translator: MappingCache) -> dict[str, Any]:
    reversed = {}
    for k, v in args.items():
        k = translator.reverse(k)
        reversed[k] = v
    return reversed

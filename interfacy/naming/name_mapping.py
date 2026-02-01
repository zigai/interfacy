from collections.abc import Callable
from typing import Any


class NameMapping:
    """Caches forward and reverse command/argument name translations."""

    def __init__(
        self, translation_fn: Callable[[str], str], ignored: set[str] | None = None
    ) -> None:
        self.translation_fn: Callable[[str], str] = translation_fn
        self.ignored_names: set[str] = ignored if ignored is not None else set()
        self.translations: dict[str, str] = {}

    def ignore(self, name: str) -> None:
        """
        Add a name to the ignore list.

        Args:
            name (str): Name to ignore.
        """
        self.ignored_names.add(name)

    def translate(self, key: str) -> str:
        """
        Translate a canonical name and record the mapping.

        Args:
            key (str): Canonical name.
        """
        if key in self.ignored_names:
            return key
        translated_key = self.translation_fn(key)
        self.translations[translated_key] = key
        return translated_key

    def reverse(self, translated: str) -> str:
        """
        Reverse a translated name to its canonical form.

        Args:
            translated (str): Translated name.
        """
        if translated in self.ignored_names:
            return translated
        return self.translations.get(translated, translated)

    def contains_key(self, name: str) -> bool:
        """
        Return True if a canonical name has been translated.

        Args:
            name (str): Canonical name to check.
        """
        return name in self.translations.values()

    def contains_translation(self, name: str) -> bool:
        """
        Return True if a translated name exists in the cache.

        Args:
            name (str): Translated name to check.
        """
        return name in self.translations


def reverse_translations(args: dict[str, Any], translator: NameMapping) -> dict[str, Any]:
    """
    Reverse all translated keys in an argument mapping.

    Args:
        args (dict[str, Any]): Argument mapping with translated keys.
        translator (NameMapping): Translator for reversing names.
    """
    reversed_args: dict[str, Any] = {}
    for key, value in args.items():
        canonical = translator.reverse(key)
        reversed_args[canonical] = value
    return reversed_args


__all__ = ["NameMapping", "reverse_translations"]

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

    def compute(self, key: str) -> str:
        """Translate a name without recording the mapping."""
        if key in self.ignored_names:
            return key
        return self.translation_fn(key)

    def record(self, key: str, translated_key: str) -> None:
        """Record a translated name mapping."""
        self.translations[translated_key] = key
        normalized_key = translated_key.replace("-", "_")
        if normalized_key != translated_key:
            self.translations[normalized_key] = key

    def translate(self, key: str) -> str:
        """Translate a canonical name and record the mapping."""
        translated_key = self.compute(key)
        if key not in self.ignored_names:
            self.record(key, translated_key)
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


def reverse_translations(args: dict[str, Any], translator: NameMapping) -> dict[str, Any]:
    """
    Reverse all translated keys in an argument mapping.

    Args:
        args (dict[str, Any]): Argument mapping with translated keys.
        translator (NameMapping): Translator for reversing names.
    """
    return {translator.reverse(key): value for key, value in args.items()}


__all__ = ["NameMapping", "reverse_translations"]

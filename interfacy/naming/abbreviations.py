from abc import abstractmethod


class AbbreviationGenerator:
    @abstractmethod
    def generate(self, value: str, taken: list[str]) -> str | None: ...


class DefaultAbbreviationGenerator(AbbreviationGenerator):
    """
    Simple abbreviation generator that tries to return a short name for a command.
    Returns None if it cannot find a short name.

    Args:
        taken (list[str]): List of taken abbreviations.
        min_len (int, optional): Minimum length of the value to abbreviate. If the value is shorter than this, None will be returned.

    Example:
        >>> AbbreviationGenerator(taken=[]).generate("hello_word")
        "h"
        >>> AbbreviationGenerator(taken=["h"]).generate("hello_word")
        "hw"
        >>> AbbreviationGenerator(taken=["hw", "h"]).generate("hello_word")
        "he"
        >>> AbbreviationGenerator(taken=["hw", "h", "he"]).generate("hello_word")
        None

    """

    def __init__(self, min_len: int = 3) -> None:
        self.min_len = min_len

    def generate(self, value: str, taken: list[str]) -> str | None:
        if value in taken:
            raise ValueError(f"'{value}' is already an abbreviation")

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
        except IndexError:
            return None
        else:
            if short_name not in taken and short_name != value:
                taken.append(short_name)
                return short_name
            return None


class NoAbbreviations(AbbreviationGenerator):
    def generate(self, value: str, taken: list[str]) -> str | None:
        return None


__all__ = [
    "AbbreviationGenerator",
    "DefaultAbbreviationGenerator",
    "NoAbbreviations",
]

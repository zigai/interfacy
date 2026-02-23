from abc import abstractmethod


class AbbreviationGenerator:
    """Interface for generating short flag abbreviations."""

    @abstractmethod
    def generate(self, value: str, taken: list[str]) -> str | None:
        """
        Return a unique abbreviation for a value or None if unavailable.

        Args:
            value (str): Source value to abbreviate.
            taken (list[str]): Already-reserved abbreviations. Modified in-place.
        """
        ...


class DefaultAbbreviationGenerator(AbbreviationGenerator):
    """
    Simple abbreviation generator that tries to return a short name for a command.
    Returns None if it cannot find a short name.

    Args:
        max_generated_len (int, optional): Maximum generated abbreviation length.

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

    def __init__(self, max_generated_len: int = 1) -> None:
        if max_generated_len < 1:
            raise ValueError("max_generated_len must be >= 1")
        self.max_generated_len = max_generated_len

    def generate(self, value: str, taken: list[str]) -> str | None:
        """
        Generate a short unique abbreviation for a value.

        Args:
            value (str): Source value to abbreviate.
            taken (list[str]): Already-reserved abbreviations. Modified in-place.

        Raises:
            ValueError: If the full value is already reserved as an abbreviation.
        """
        if value in taken:
            raise ValueError(f"'{value}' is already an abbreviation")

        name_split = value.split("_")
        if not name_split:
            return None

        candidates = [
            name_split[0][0],
            "".join([part[0] for part in name_split if part]),
            name_split[0][:2],
        ]

        for candidate in candidates:
            if (
                candidate
                and len(candidate) <= self.max_generated_len
                and candidate not in taken
                and candidate != value
            ):
                taken.append(candidate)
                return candidate
        return None


class NoAbbreviations(AbbreviationGenerator):
    """Abbreviation generator that disables short flags."""

    def generate(
        self,
        value: str,  # noqa: ARG002 - interface contract
        taken: list[str],  # noqa: ARG002 - interface contract
    ) -> str | None:
        """
        Return None to indicate no abbreviation is available.

        Args:
            value (str): Source value to abbreviate.
            taken (list[str]): Already-reserved abbreviations.
        """
        return None


__all__ = [
    "AbbreviationGenerator",
    "DefaultAbbreviationGenerator",
    "NoAbbreviations",
]

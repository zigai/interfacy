from .abbreviations import AbbreviationGenerator, DefaultAbbreviationGenerator, NoAbbreviations
from .command_naming import CommandNameRegistry
from .flag_strategy import (
    DefaultFlagStrategy,
    FlagStrategy,
    FlagStyle,
    TranslationMode,
    build_name_mapping,
)
from .name_mapping import NameMapping, reverse_translations

__all__ = [
    "AbbreviationGenerator",
    "CommandNameRegistry",
    "DefaultAbbreviationGenerator",
    "DefaultFlagStrategy",
    "FlagStrategy",
    "FlagStyle",
    "NameMapping",
    "NoAbbreviations",
    "TranslationMode",
    "build_name_mapping",
    "reverse_translations",
]

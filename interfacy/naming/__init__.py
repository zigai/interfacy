from .abbervations import AbbrevationGenerator, DefaultAbbrevationGenerator, NoAbbrevations
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
    "CommandNameRegistry",
    "DefaultFlagStrategy",
    "FlagStrategy",
    "FlagStyle",
    "NameMapping",
    "TranslationMode",
    "build_name_mapping",
    "reverse_translations",
]

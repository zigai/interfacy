from collections.abc import Callable
from typing import Literal, Protocol

from objinspect import Parameter
from stdl.st import kebab_case, snake_case

from interfacy.naming.abbreviations import AbbreviationGenerator
from interfacy.naming.name_mapping import NameMapping
from interfacy.util import is_list_or_list_alias

FlagStyle = Literal["keyword_only", "required_positional"]
TranslationMode = Literal["none", "kebab", "snake"]

NAME_TRANSLATORS: dict[TranslationMode, Callable[[str], str]] = {
    "none": lambda s: s,
    "kebab": kebab_case,
    "snake": snake_case,
}


def build_name_mapping(mode: TranslationMode) -> NameMapping:
    if mode not in NAME_TRANSLATORS:
        raise ValueError(
            f"Invalid flag translation mode: {mode}. "
            f"Valid modes are: {', '.join(NAME_TRANSLATORS.keys())}"
        )
    return NameMapping(NAME_TRANSLATORS[mode])


class FlagStrategy(Protocol):
    argument_translator: NameMapping
    command_translator: NameMapping
    style: FlagStyle
    translation_mode: TranslationMode

    def get_arg_flags(
        self,
        name: str,
        param: Parameter,
        taken_flags: list[str],
        abbrev_gen: AbbreviationGenerator,
    ) -> tuple[str, ...]: ...


class DefaultFlagStrategy(FlagStrategy):
    def __init__(
        self,
        style: FlagStyle = "required_positional",
        translation_mode: TranslationMode = "kebab",
    ) -> None:
        self.style = style
        self.translation_mode = translation_mode
        self._nargs_list_count = 0

        self.argument_translator = build_name_mapping(self.translation_mode)
        self.command_translator = build_name_mapping(self.translation_mode)

    def get_arg_flags(
        self,
        name: str,
        param: Parameter,
        taken_flags: list[str],
        abbrev_gen: AbbreviationGenerator,
    ) -> tuple[str, ...]:
        """
        Generate CLI flag names for a given parameter based on its name and already taken flags.

        Args:
            name (str): The name of the parameter for which to generate flags.
            param (Parameter): Parameter object containing type and other metadata.
            taken_flags (list[str]): Flags that are already in use.
            abbrev_gen (AbbreviationGenerator): AbbreviationGenerator instance.

        Returns:
            tuple[str, ...]: A tuple containing the long flag (and short flag if applicable).
        """
        is_bool_flag = param.is_typed and param.type is bool
        is_positional_list = (
            is_list_or_list_alias(param.type)
            and param.is_required
            and self.style == "required_positional"
        )

        # Return positional argument?
        if is_positional_list and self._nargs_list_count < 1:
            self._nargs_list_count += 1
            return (name,)
        if (
            not is_bool_flag
            and not is_positional_list
            and param.is_required
            and self.style == "required_positional"
        ):
            return (name,)

        if len(name) == 1:
            flag_long = f"-{name}".strip()
        else:
            flag_long = f"--{name}".strip()

        flags = (flag_long,)
        if is_bool_flag:
            return flags

        if flag_short := abbrev_gen.generate(name, taken_flags):
            flag_short = flag_short.strip()
            if flag_short != name:
                flags = (f"-{flag_short}", flag_long)
        return flags


__all__ = [
    "DefaultFlagStrategy",
    "FlagStrategy",
    "FlagStyle",
    "TranslationMode",
    "build_name_mapping",
]

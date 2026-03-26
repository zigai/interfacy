from collections.abc import Callable
from dataclasses import dataclass
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
    """
    Build a NameMapping for a translation mode.

    Args:
        mode (TranslationMode): Translation mode to use.

    Raises:
        ValueError: If the translation mode is unsupported.
    """
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


@dataclass
class FlagAllocationState:
    """Per-command flag allocation state for positional parameters."""

    consumed_required_list_positional: bool = False


class _FlagParamView:
    """Proxy parameter that overrides selected attributes without losing the original shape."""

    def __init__(self, param: Parameter, **overrides: object) -> None:
        self._param = param
        self._overrides = overrides

    def __getattr__(self, name: str) -> object:
        if name in self._overrides:
            return self._overrides[name]
        return getattr(self._param, name)


def _is_required_list_positional_candidate(strategy: FlagStrategy, param: Parameter) -> bool:
    return (
        strategy.style == "required_positional"
        and param.is_required
        and not (param.is_typed and param.type is bool)
        and is_list_or_list_alias(param.type)
    )


def get_arg_flags_for_parameter(
    strategy: FlagStrategy,
    name: str,
    param: Parameter,
    taken_flags: list[str],
    abbrev_gen: AbbreviationGenerator,
    *,
    allocation_state: FlagAllocationState | None = None,
) -> tuple[str, ...]:
    """
    Generate flags using build-local positional allocation for required list parameters.

    The strategy remains stateless. Callers that want "first greedy required list stays
    positional" can pass a local allocation state for the current command/build.
    """
    if _is_required_list_positional_candidate(strategy, param):
        if allocation_state is None:
            return (name,)
        if not allocation_state.consumed_required_list_positional:
            allocation_state.consumed_required_list_positional = True
            return (name,)
        param = _FlagParamView(param, is_required=False)

    return strategy.get_arg_flags(name, param, taken_flags, abbrev_gen)


class DefaultFlagStrategy(FlagStrategy):
    """
    Default flag strategy for generating CLI flag names.

    Args:
        style (FlagStyle): Flag style for required/optional parameters.
        translation_mode (TranslationMode): Name translation mode.
        nested_separator (str): Separator for nested model paths.
    """

    def __init__(
        self,
        style: FlagStyle = "required_positional",
        translation_mode: TranslationMode = "kebab",
        nested_separator: str = ".",
    ) -> None:
        self.style = style
        self.translation_mode = translation_mode
        self.nested_separator = nested_separator

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
        if not is_bool_flag and param.is_required and self.style == "required_positional":
            return (name,)

        flag_long = f"--{name}".strip() if is_bool_flag or len(name) > 1 else f"-{name}".strip()

        flags: tuple[str, ...] = (flag_long,)

        abbrev_name = name

        if is_bool_flag:
            default_value = param.default if param.has_default else False
            if default_value is True:
                abbrev_name = f"no-{name}"

        if flag_short := abbrev_gen.generate(abbrev_name, taken_flags):
            flag_short = flag_short.strip()
            if flag_short and flag_short not in (name, abbrev_name):
                flags = (f"-{flag_short}", flag_long)

        return flags


__all__ = [
    "DefaultFlagStrategy",
    "FlagAllocationState",
    "FlagStrategy",
    "FlagStyle",
    "TranslationMode",
    "build_name_mapping",
    "get_arg_flags_for_parameter",
]

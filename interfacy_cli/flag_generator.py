import typing as T

from objinspect import Parameter
from stdl.st import kebab_case, snake_case

from interfacy_cli.util import AbbrevationGenerator, TranslationMapper, is_list_or_list_alias

FlagsStyle = T.Literal["keyword_only", "required_positional"]


class FlagGenerator(T.Protocol):
    argument_translator: TranslationMapper
    command_translator: TranslationMapper
    style: FlagsStyle

    def get_arg_flags(
        self,
        name: str,
        param: Parameter,
        taken_flags: list[str],
        abbrev_gen: AbbrevationGenerator,
    ) -> tuple[str, ...]: ...


class BasicFlagGenerator(FlagGenerator):
    flag_translate_fn = {"none": lambda s: s, "kebab": kebab_case, "snake": snake_case}

    def __init__(
        self,
        style: FlagsStyle = "required_positional",
        translation_mode: T.Literal["none", "kebab", "snake"] = "kebab",
    ) -> None:
        self.style = style
        self.translation_mode = translation_mode
        self.argument_translator = self._get_flag_translator()
        self.command_translator = self._get_flag_translator()
        self._nargs_list_count = 0

    def _get_flag_translator(self) -> TranslationMapper:
        if self.translation_mode not in self.flag_translate_fn:
            raise ValueError(
                f"Invalid flag translation mode: {self.translation_mode}. "
                f"Valid modes are: {', '.join(self.flag_translate_fn.keys())}"
            )
        return TranslationMapper(self.flag_translate_fn[self.translation_mode])

    def get_arg_flags(
        self,
        name: str,
        param: Parameter,
        taken_flags: list[str],
        abbrev_gen: AbbrevationGenerator,
    ) -> tuple[str, ...]:
        """
        Generate CLI flag names for a given parameter based on its name and already taken flags.

        Args:
            param_name (str): The name of the parameter for which to generate flags.
            taken_flags (list[str]): A list of flags that are already in use.

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


__all__ = ["FlagsStyle", "FlagGenerator", "BasicFlagGenerator"]

from interfacy_core.interfacy_param import InterfacyParameter
from interfacy_core.util import type_as_str
from stdl.str_u import colored

from interfacy_cli.themes import DEFAULT


class HelpStringTheme:
    def __init__(
        self, type_clr: str, default_clr: str, sep: str, simplify_type: bool = False
    ) -> None:
        self.type_clr = type_clr
        self.default_cr = default_clr
        self.sep = sep
        self.simplify_type = simplify_type

    @property
    def dict(self):
        return {
            "type_clr": self.type_clr,
            "default_clr": self.default_cr,
            "sep": self.sep,
            "simplify_type": self.simplify_type,
        }


def param_helpstring(param: InterfacyParameter, theme: HelpStringTheme = DEFAULT) -> str:
    if param.is_required and not param.is_typed:
        return ""
    help_str = []
    if param.is_typed:
        typestr = type_as_str(param.type)
        if theme.simplify_type:
            typestr = typestr.split(".")[-1]
        help_str.append(colored(typestr, theme.type_clr))
    if param.is_typed and param.is_optional:
        help_str.append(theme.sep)
    if param.is_optional:
        help_str.append(f"{colored(param.default, theme.default_cr)}")
    help_str = "".join(help_str)
    if param.description is not None:
        help_str = f"{param.description} [{help_str}]"
    return help_str

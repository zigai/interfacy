import inspect

from stdl.str_util import ColorANSI, str_with_color

from interfacy.util import type_as_str

EMPTY = inspect._empty
DEFAULT_CLI_THEME = {"type": ColorANSI.LIGHT_YELLOW, "value": ColorANSI.LIGHT_BLUE}


class InterfacyParameter:

    def __init__(self, param: inspect.Parameter) -> None:
        self.type = param.annotation
        self.name = param.name
        self.default = param.default

    @property
    def dict(self):
        return {
            "name": self.name,
            "type": self.type,
            "default": self.default,
        }

    def __repr__(self):
        return f"InterfacyParameter(type={self.type}, name={self.name}, default={self.default})"

    @property
    def is_typed(self) -> bool:
        return self.type != EMPTY

    @property
    def is_required(self) -> bool:
        return self.default == EMPTY

    @property
    def flag_name(self) -> str:
        return f"--{self.name}"

    def get_help_str(self, theme) -> str:
        if self.is_required and not self.is_typed:
            return ""
        help_str = []
        if self.is_typed:
            help_str.append(str_with_color(type_as_str(self.type), theme['type']))
        if not self.is_required:
            help_str.append(f"default: {str_with_color(self.default, theme['value'])}")
        help_str = ", ".join(help_str)
        return help_str

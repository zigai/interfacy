import enum
import inspect
import types
import typing

from stdl.str_util import Color, str_with_color

from interfacy.cli_parsers import CLI_PARSER
from interfacy.util import type_as_str

EMPTY = inspect._empty
SIMPLE_TYPES = [str, int, float, bool]

SpecialGenericAlias = typing._SpecialGenericAlias
UnionGenericAlias = typing._UnionGenericAlias
from typing import Any


class ParameterKind(enum.Enum):
    BASIC = 1
    UNSUPPORTED = 2
    UNION = 3
    ALIAS = 4
    SPECIAL = 5


class InterfacyParameter:
    DEFAULT_CLI_THEME = {"type": Color.LIGHT_YELLOW, "default": Color.LIGHT_BLUE}

    def __init__(
        self,
        name: str,
        type: Any = EMPTY,
        default: Any = EMPTY,
        description: str | None = None,
    ) -> None:
        self.name = name
        self.type = type
        self.default = default
        self.description = description

    @property
    def dict(self):
        return {
            "name": self.name,
            "type": self.type,
            "default": self.default,
            "description": self.description,
        }

    def __repr__(self):
        data = f"name={self.name}, type={self.type}, default={self.default}, description={self.description}"
        return f"Parameter({data})"

    @property
    def kind(self) -> ParameterKind:
        if self.type == EMPTY:
            return ParameterKind.BASIC
        if self.type in SIMPLE_TYPES:
            return ParameterKind.BASIC
        if self.type in CLI_PARSER.keys():
            return ParameterKind.SPECIAL
        if type(self.type) in [types.UnionType, UnionGenericAlias]:
            return ParameterKind.UNION
        if type(self.type) in [types.GenericAlias, SpecialGenericAlias]:
            return ParameterKind.ALIAS
        return ParameterKind.UNSUPPORTED

    @property
    def is_typed(self) -> bool:
        return self.type != EMPTY

    @property
    def is_required(self) -> bool:
        return self.default == EMPTY

    @property
    def is_optional(self) -> bool:
        return not self.is_required

    @property
    def flag_name(self) -> str:
        return f"--{self.name}"

    def help_string(self, theme=DEFAULT_CLI_THEME) -> str:
        if self.is_required and not self.is_typed:
            return ""
        help_str = []

        if self.is_typed:
            if theme is not None:
                help_str.append(str_with_color(type_as_str(self.type), theme['type']))
            else:
                help_str.append(type_as_str(self.type))

        if self.is_optional:
            if theme is not None:
                help_str.append(f"default: {str_with_color(self.default, theme['default'])}")
            else:
                help_str.append(f"default: {self.default}")

        help_str = ", ".join(help_str)
        if self.description is not None:
            help_str = f"{self.description} [{help_str}]"
        return help_str

    @classmethod
    def from_inspect_param(cls, param: inspect.Parameter, description: str | None = None):
        return cls(
            name=param.name,
            type=param.annotation,
            default=param.default,
            description=description,
        )

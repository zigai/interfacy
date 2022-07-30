import enum
import inspect
import types
import typing
from typing import Any

from stdl.str_util import Color, str_with_color

from interfacy.cli.helpstr_theme import HelpStringTheme
from interfacy.constants import EMPTY
from interfacy.util import type_as_str

CLI_SIMPLE_TYPES = (str, int, bool)


class UnionTypeParameter:

    def __init__(self, params: tuple) -> None:
        self.params = params


class ParameterKind(enum.Enum):
    BASIC = 1
    UNSUPPORTED = 2
    UNION = 3
    ALIAS = 4
    SPECIAL = 5


class InterfacyParameter:

    def __init__(
        self,
        name: str,
        type: Any = EMPTY,
        default: Any = EMPTY,
        description: str | None = None,
        owner: str | None = None,
    ) -> None:
        self.name = name
        self.type = type
        self.default = default
        self.description = description
        self.owner = owner

    @property
    def dict(self):
        return {
            "name": self.name,
            "type": self.type,
            "default": self.default,
            "description": self.description,
        }

    def __repr__(self):
        data = f"name={self.name}, type={self.type}, default={self.default}, description={self.description}, owner={self.owner}"
        return f"Parameter({data})"

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

    def help_string(self, theme: HelpStringTheme) -> str:
        if self.is_required and not self.is_typed:
            return ""
        help_str = []

        if self.is_typed:
            typestr = type_as_str(self.type)
            if theme.slice_typename:
                typestr = typestr.split(".")[-1]
            help_str.append(str_with_color(typestr, theme.type))
        if self.is_typed and self.is_optional:
            help_str.append(theme.sep)
        if self.is_optional:
            help_str.append(f"{str_with_color(self.default, theme.default)}")

        help_str = "".join(help_str)
        if self.description is not None:
            help_str = f"{self.description} [{help_str}]"
        return help_str

    @classmethod
    def from_inspect_param(
        cls,
        param: inspect.Parameter,
        description: str | None = None,
        owner: str | None = None,
    ):
        return cls(
            name=param.name,
            type=param.annotation,
            default=param.default,
            description=description,
            owner=owner,
        )

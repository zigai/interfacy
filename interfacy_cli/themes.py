from dataclasses import dataclass
from typing import Type

from objinspect import Class, Function, Method, Parameter
from objinspect.typing import (
    get_enum_choices,
    get_literal_choices,
    is_enum,
    is_or_contains_literal,
    is_union_type,
    type_args,
    type_name,
)
from stdl.st import FG, BackgroundColor, ForegroundColor, Style, colored

from interfacy_cli.flag_generator import FlagGenerator
from interfacy_cli.util import simplified_type_name


@dataclass
class TextStyle:
    color: ForegroundColor | str | None = None
    background: BackgroundColor | str | None = None
    style: Style | str | None = None


def with_style(text: str, style: TextStyle) -> str:
    return colored(text, color=style.color, background=style.background, style=style.style)


def colored_type(
    t: Type,
    style: TextStyle,
    simplify: bool = True,
) -> str:
    text = type_name(t)
    if simplify:
        text = simplified_type_name(text)
    NO_COLOR_CHARS = "[](){}|,?"
    parts = []
    part = []
    for char in text:
        if char in NO_COLOR_CHARS:
            parts.append(with_style("".join(part), style))
            part.clear()
            parts.append(char)
        else:
            part.append(char)
    parts.append(with_style("".join(part), style))
    return "".join(parts)


import enum
from typing import Literal, Type


def get_choices(t: Type) -> tuple | None:
    if is_or_contains_literal(t):
        return get_literal_choices(t)
    if is_enum(t):
        return get_enum_choices(t)
    if is_union_type(t):
        args = type_args(t)
        choices = []
        for i in args:
            print(i)
            if is_enum(i):
                choices.extend(get_enum_choices(i))
            elif is_or_contains_literal(i):
                choices.extend(get_literal_choices(i))
        return tuple(choices)
    return None


class DefaultTheme:
    style_type: TextStyle = TextStyle(color="green")
    style_default: TextStyle = TextStyle(color="light_blue")
    style_description: TextStyle = TextStyle(color="white")
    style_string: TextStyle = TextStyle(color="yellow")
    style_extra_data: TextStyle = TextStyle(color="gray")

    commands_title: str = "commands:"
    prefix_choices: str = "choices: "
    prefix_default: str = "default= "
    prefix_type: str = "type: "
    required_indicator: str = "(" + colored("*", color=FG.RED) + ")"

    clear_metavar: bool = True
    simplify_types: bool = True
    enable_required_indicator: bool = True

    required_indicator_pos: Literal["left", "right"] = "right"
    min_ljust: int = 19
    command_skips: list[str] = ["__init__"]
    flag_generator: FlagGenerator = None  # type:ignore

    def _get_ljust(self, commands: list[Class | Function | Method]) -> int:
        return max(self.min_ljust, max([len(i.name) for i in commands]))

    def _get_param_extra_help(self, param: Parameter) -> str:
        parts: list[str] = []
        if param.is_typed and param.type is not bool:
            if choices := get_choices(param.type):
                param_info = with_style(self.prefix_choices, self.style_extra_data) + ", ".join(
                    [with_style(i, self.style_string) for i in choices]
                )
                if not param.is_required:
                    default_text = with_style(
                        self.prefix_default, self.style_extra_data
                    ) + with_style(str(param.default), self.style_default)
                    param_info += default_text
            else:
                param_info = with_style(self.prefix_type, self.style_extra_data) + colored_type(
                    param.type, self.style_type
                )
            parts.append(param_info)

        if param.is_optional and param.default is not None and param.type is not bool:
            parts.append(", ")
            parts.append(
                with_style(self.prefix_default, self.style_extra_data)
                + with_style(str(param.default), self.style_default)
            )

        if not parts:
            return ""

        return f"[{''.join(parts)}]"

    def format_description(self, description: str) -> str:
        return description

    def get_help_for_parameter(self, param: Parameter) -> str:
        """
        Returns a parameter helpstring that should be passed as help to argparse.ArgumentParser
        """
        if param.is_required and not param.is_typed:
            return ""
        parts: list[str] = []

        # Handle boolean parameters differently
        if param.type is bool:
            if param.description is not None:
                description = param.description
                if not description.endswith((".", "?", "!")):
                    description = description + "."
                parts.append(f"{with_style(description, self.style_description)}")
        else:
            if param.description is not None:
                parts.append(f"{with_style(param.description, self.style_description)} ")
            parts.append(self._get_param_extra_help(param))

        text = "".join(parts)
        if param.is_required:
            if self.required_indicator_pos == "left":
                text = f"{self.required_indicator} {text}"
            else:
                text = f"{text} {self.required_indicator}"
        return text

    def get_command_description(
        self, command: Class | Function | Method, ljust: int, name: str | None = None
    ) -> str:
        name = name or command.name
        command_name = self.flag_generator.command_translator.translate(name)
        name = f"   {command_name}".ljust(ljust)
        return f"{name} {with_style(command.description, self.style_description)}"

    def get_help_for_class(self, command: Class) -> str:
        ljust = self._get_ljust(command.methods)  # type: ignore
        lines = [self.commands_title]
        for method in command.methods:
            if method.name in self.command_skips:
                continue
            lines.append(self.get_command_description(method, ljust))
        return "\n".join(lines)

    def get_help_for_multiple_commands(self, commands: dict[str, Class | Function | Method]) -> str:
        ljust = self._get_ljust(commands.values())  # type: ignore
        lines = [self.commands_title]
        for name, command in commands.items():
            lines.append(self.get_command_description(command, ljust, name))
        return "\n".join(lines)


class PlainTheme(DefaultTheme):
    style_type = TextStyle(color=FG.WHITE)
    style_default = TextStyle(color=FG.WHITE)
    style_description = TextStyle(color=FG.WHITE)
    required_indicator = "(*)"


__all__ = ["DefaultTheme", "PlainTheme"]

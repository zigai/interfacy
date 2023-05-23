from typing import Callable

from objinspect import Class, Function, Method, Parameter
from objinspect.util import type_to_str
from stdl.str_u import FG, colored

from interfacy_cli.util import simplify_type


def with_style(text: str, style: dict) -> str:
    return colored(text, **style)


class InterfacyTheme:
    clear_metavar: bool = True
    simplify_types = True
    min_ljust = 19
    style_type: dict = dict(color=FG.GREEN)
    style_default: dict = dict(color=FG.LIGHT_BLUE)
    style_description: dict = dict(color=FG.GRAY)
    sep = " = "
    command_skips = ["__init__"]
    commands_title = "commands:"
    required_indicator = "(" + colored("*", color=FG.RED) + ") "
    name_translate_func: Callable = None

    def _get_ljust(self, commands: list[Class | Function | Method]) -> int:
        return max(self.min_ljust, max([len(i.name) for i in commands]))

    def _translate_name(self, name: str) -> str:
        return self.name_translate_func(name) if self.name_translate_func else name

    def format_description(self, description: str) -> str:
        return description

    def get_parameter_help(self, param: Parameter) -> str:
        """
        Returns a parameter helpstring that should be paseed as help to argparse.ArgumentParser
        """
        if param.is_required and not param.is_typed:
            return ""
        h = []

        if param.description is not None:
            fill = " "
            h.append(f"{with_style(param.description, self.style_description)} | {fill}")

        if param.is_typed:
            type_str = type_to_str(param.type)
            if self.simplify_types:
                type_str = simplify_type(type_str)
            h.append(with_style(type_str, self.style_type))

        if param.is_optional and param.default is not None:
            if param.is_typed:
                h.append(self.sep)
            h.append(with_style(param.default, self.style_default))

        h = "".join(h)

        if param.is_required:
            h = f"{h} {self.required_indicator}"
        return h

    def get_command_description(self, command: Class | Function | Method, ljust: int) -> str:
        command_name = self._translate_name(command.name)
        name = f"  {command_name}".ljust(ljust)
        return f"{name} {with_style(command.description, self.style_description)}"

    def get_commands_help_class(self, command: Class) -> str:
        ljust = self._get_ljust(command.methods)  # type: ignore
        h = [self.commands_title]
        for method in command.methods:
            if method.name in self.command_skips:
                continue
            h.append(self.get_command_description(method, ljust))
        return "\n".join(h)

    def get_commands_help_multiple(self, commands: list[Class | Function | Method]) -> str:
        ljust = self._get_ljust(commands)  # type: ignore
        h = [self.commands_title]
        for command in commands:
            h.append(self.get_command_description(command, ljust))
        return "\n".join(h)


class PlainTheme(InterfacyTheme):
    style_type = dict(color=FG.WHITE)
    style_default = dict(color=FG.WHITE)
    style_description = dict(color=FG.WHITE)
    required_indicator = "(required)"


class LegacyTheme(InterfacyTheme):
    simplify_types = False
    sep = ", default: "
    type_color = FG.LIGHT_YELLOW
    style_type = dict(color=FG.LIGHT_YELLOW)
    param_default_color = dict(color=FG.LIGHT_BLUE)


__all__ = [
    "InterfacyTheme",
    "PlainTheme",
    "LegacyTheme",
]

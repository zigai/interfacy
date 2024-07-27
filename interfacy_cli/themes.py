import typing as T

from objinspect import Class, Function, Method, Parameter
from objinspect.typing import type_name
from stdl.st import FG, colored

from interfacy_cli.util import simplified_type_name


def with_style(text: str, style: dict[T.Literal["color", "background", "style"], str]) -> str:
    return colored(text, **style)


class InterfacyTheme:
    clear_metavar: bool = True
    simplify_types: bool = True
    min_ljust: int = 19
    style_type: dict = dict(color=FG.GREEN)
    style_default: dict = dict(color=FG.LIGHT_BLUE)
    style_description: dict = dict(color=FG.WHITE)
    sep: str = " = "
    command_skips: list[str] = ["__init__"]
    commands_title: str = "commands:"
    required_indicator: str = "(" + colored("*", color=FG.RED) + ") "
    translate_name: T.Callable = None  # type:ignore

    def _get_ljust(self, commands: list[Class | Function | Method]) -> int:
        return max(self.min_ljust, max([len(i.name) for i in commands]))

    def _translate_name(self, name: str) -> str:
        return self.translate_name(name) if self.translate_name else name

    def format_description(self, description: str) -> str:
        return description

    def get_parameter_help(self, param: Parameter) -> str:
        """
        Returns a parameter helpstring that should be passed as help to argparse.ArgumentParser
        """
        if param.is_required and not param.is_typed:
            return ""

        h = []
        # Handle boolean parameters differently
        if param.type is bool:
            if param.description is not None:
                description = param.description
                if not description.endswith("."):
                    description = description + "."
                h.append(f"{with_style(description, self.style_description)}")

            if param.default is True:
                h.append(
                    with_style(
                        " Enabled by default - passing this flag disables it.",
                        self.style_description,
                    )
                )
        else:
            if param.description is not None:
                h.append(f"{with_style(param.description, self.style_description)} | ")

            if param.is_typed and param.type is not bool:
                type_str = type_name(param.type)
                if self.simplify_types:
                    type_str = simplified_type_name(type_str)
                h.append(with_style(type_str, self.style_type))

            if param.is_optional and param.default is not None and param.type is not bool:
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
        lines = [self.commands_title]
        for method in command.methods:
            if method.name in self.command_skips:
                continue
            lines.append(self.get_command_description(method, ljust))
        return "\n".join(lines)

    def get_commands_help_multiple(self, commands: list[Class | Function | Method]) -> str:
        ljust = self._get_ljust(commands)  # type: ignore
        lines = [self.commands_title]
        for command in commands:
            lines.append(self.get_command_description(command, ljust))
        return "\n".join(lines)


class InterfacyDimTheme(InterfacyTheme):
    style_description = dict(color=FG.GRAY)


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

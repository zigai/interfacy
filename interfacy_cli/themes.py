from dataclasses import dataclass

from objinspect import Class, Function, Method, Parameter
from objinspect.typing import get_literal_choices, is_direct_literal, type_name
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


class DefaultTheme:
    style_type: TextStyle = TextStyle(color="green")
    style_default: TextStyle = TextStyle(color="light_white")
    style_description: TextStyle = TextStyle(color="white")
    style_string: TextStyle = TextStyle(color="yellow")

    clear_metavar: bool = True
    simplify_types: bool = True
    min_ljust: int = 19
    sep: str = " = "
    commands_title: str = "commands:"
    literal_sep: str = " | "
    required_indicator: str = "(" + colored("*", color=FG.RED) + ") "
    command_skips: list[str] = ["__init__"]
    flag_generator: FlagGenerator = None  # type:ignore

    def _get_ljust(self, commands: list[Class | Function | Method]) -> int:
        return max(self.min_ljust, max([len(i.name) for i in commands]))

    def _get_type_description(self, t):
        if is_direct_literal(t):
            choices = [with_style(i, self.style_string) for i in get_literal_choices(t)]
            return self.literal_sep.join(choices)

        type_str = type_name(t)
        if self.simplify_types:
            type_str = simplified_type_name(type_str)

        return with_style(type_str, self.style_type)

    def format_description(self, description: str) -> str:
        return description

    def get_help_for_parameter(self, param: Parameter) -> str:
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
        else:
            if param.description is not None:
                h.append(f"{with_style(param.description, self.style_description)} | ")

            if param.is_typed and param.type is not bool:
                h.append(self._get_type_description(param.type))

            if param.is_optional and param.default is not None and param.type is not bool:
                if param.is_typed:
                    h.append(self.sep)
                h.append(with_style(str(param.default), self.style_default))

        h = "".join(h)

        if param.is_required:
            h = f"{h} {self.required_indicator}"

        return h

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


class DimTheme(DefaultTheme):
    style_description = TextStyle(color=FG.GRAY)


class PlainTheme(DefaultTheme):
    style_type = TextStyle(color=FG.WHITE)
    style_default = TextStyle(color=FG.WHITE)
    style_description = TextStyle(color=FG.WHITE)
    required_indicator = "(required)"


class LegacyTheme(DefaultTheme):
    simplify_types = False
    sep = ", default: "
    type_color = FG.LIGHT_YELLOW
    style_type = TextStyle(color=FG.LIGHT_YELLOW)
    param_default_color = dict(color=FG.LIGHT_BLUE)


__all__ = [
    "DefaultTheme",
    "PlainTheme",
    "LegacyTheme",
]

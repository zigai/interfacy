from typing import ClassVar, Literal

from objinspect import Class, Function, Method, Parameter
from objinspect.typing import get_choices
from objinspect.util import colored_type
from stdl.st import TextStyle, colored, with_style

from interfacy.command import Command
from interfacy.naming import CommandNameRegistry, FlagStrategy


class ParserTheme:
    style_type: TextStyle = TextStyle(color="green")
    style_default: TextStyle = TextStyle(color="light_blue")
    style_description: TextStyle = TextStyle(color="white")
    style_string: TextStyle = TextStyle(color="yellow")
    style_extra_data: TextStyle = TextStyle(color="gray")

    commands_title: str = "commands:"
    prefix_choices: str = "choices: "
    prefix_default: str = "default="
    prefix_type: str = "type: "
    required_indicator: str = "(" + colored("*", color="red") + ")"

    clear_metavar: bool = True
    simplify_types: bool = True
    enable_required_indicator: bool = True

    required_indicator_pos: Literal["left", "right"] = "right"
    min_ljust: int = 19
    command_skips: ClassVar[list[str]] = ["__init__"]
    flag_generator: FlagStrategy = None  # type:ignore
    name_registry: CommandNameRegistry | None = None

    def _get_ljust(self, commands: list[Class | Function | Method]) -> int:
        return max(self.min_ljust, max([len(i.name) for i in commands]))

    def _get_param_extra_help(self, param: Parameter) -> str:
        parts: list[str] = []
        default_added = False
        if param.is_typed and param.type is not bool:
            if choices := get_choices(param.type):
                param_info = with_style(self.prefix_choices, self.style_extra_data) + ", ".join(
                    [with_style(i, self.style_string) for i in choices]
                )
                if not param.is_required:
                    default_text = with_style(
                        self.prefix_default, self.style_extra_data
                    ) + with_style(str(param.default), self.style_default)
                    param_info += ", " + default_text
                    default_added = True
            else:
                param_info = with_style(self.prefix_type, self.style_extra_data) + colored_type(
                    param.type, self.style_type
                )
            parts.append(param_info)

        if (
            param.is_optional
            and param.default is not None
            and param.type is not bool
            and not default_added
        ):
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
        """Returns a parameter helpstring that should be passed as help to argparse.ArgumentParser"""
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

    def _format_command_display_name(self, name: str, aliases: tuple[str, ...] = ()) -> str:
        if not aliases:
            return name
        alias_text = ", ".join(aliases)
        return f"{name} ({alias_text})"

    def get_command_description(
        self,
        command: Class | Function | Method,
        ljust: int,
        name: str | None = None,
        aliases: tuple[str, ...] = (),
    ) -> str:
        name = name or command.name
        command_name = self._format_command_display_name(name, aliases)
        name_column = f"   {command_name}".ljust(ljust)
        description = command.description or ""
        return f"{name_column} {with_style(description, self.style_description)}"

    def get_help_for_class(self, command: Class) -> str:
        ljust = self._get_ljust(command.methods)  # type: ignore
        lines = [self.commands_title]
        for method in command.methods:
            if method.name in self.command_skips:
                continue
            method_name = self.flag_generator.command_translator.translate(method.name)
            lines.append(self.get_command_description(method, ljust, method_name))
        return "\n".join(lines)

    def get_help_for_multiple_commands(self, commands: dict[str, Command]) -> str:
        display_names = [
            self._format_command_display_name(cmd.name, cmd.aliases) for cmd in commands.values()
        ]
        max_display = max([len(name) for name in display_names], default=0)
        ljust = max(self.min_ljust, max_display)
        lines = [self.commands_title]
        for name, command in commands.items():
            lines.append(
                self.get_command_description(
                    command.obj,
                    ljust,
                    name,
                    command.aliases,
                )
            )
        return "\n".join(lines)


class PlainParserTheme(ParserTheme):
    style_type: TextStyle = TextStyle(color="white")
    style_default: TextStyle = TextStyle(color="white")
    style_description: TextStyle = TextStyle(color="white")
    style_string: TextStyle = TextStyle(color="white")
    style_extra_data: TextStyle = TextStyle(color="white")
    required_indicator = "(*)"


__all__ = ["ParserTheme", "PlainParserTheme"]

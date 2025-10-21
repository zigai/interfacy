import os
import re
from re import Match
from typing import TYPE_CHECKING, ClassVar, Literal

from objinspect import Class, Function, Method, Parameter
from objinspect.typing import get_choices
from stdl.st import TextStyle, ansi_len, colored, with_style

from interfacy.naming import CommandNameRegistry, FlagStrategy
from interfacy.util import format_type_for_help

if TYPE_CHECKING:  # pragma: no cover
    from interfacy.schema.schema import Command


class InterfacyColors:
    """Base color theme for interfacy"""

    type: TextStyle = TextStyle(color="green")
    default: TextStyle = TextStyle(color="light_blue")
    description: TextStyle = TextStyle(color="white")
    string: TextStyle = TextStyle(color="yellow")
    extra_data: TextStyle = TextStyle(color="gray")
    flag_short: TextStyle = TextStyle(color="white")
    flag_long: TextStyle = TextStyle(color="white")
    flag_positional: TextStyle = TextStyle(color="white")


class HelpLayout:
    style: InterfacyColors = InterfacyColors()

    commands_title: str = "commands:"
    prefix_choices: str = "choices: "
    prefix_default: str = "default="
    prefix_type: str = "type: "
    required_indicator: str = "(*)"

    clear_metavar: bool = True
    simplify_types: bool = True
    enable_required_indicator: bool = True

    required_indicator_pos: Literal["left", "right"] = "right"
    min_ljust: int = 19
    command_skips: ClassVar[list[str]] = ["__init__"]
    flag_generator: FlagStrategy = None  # type:ignore
    name_registry: CommandNameRegistry | None = None

    format_option: str | None = None
    format_positional: str | None = None
    help_position: int | None = None
    default_field_width: int = 7
    default_label_for_help: str = "default"
    include_metavar_in_flag_display: bool = True
    short_flag_width: int = 6
    long_flag_width: int = 18
    pos_flag_width: int = 24
    min_total_flag_width: int = 24
    PRE_FMT_PREFIX = "\x00FMT:"

    layout_mode: Literal["auto", "adaptive", "template"] = "auto"

    # "bold":  remove backticks in docstring and make text bold
    # "strip": remove backticks in docstring and leave plain text
    doc_inline_code_mode: Literal["bold", "strip"] = "bold"

    def _format_doc_text(self, text: str) -> str:
        """Format inline code spans wrapped in backticks in docstrings."""
        if not text:
            return text

        def strip_triple_backtick(match: Match[str]) -> str:
            return match.group(1)

        text = re.sub(r"```[a-zA-Z0-9_+\-]*\n([\s\S]*?)```", strip_triple_backtick, text)

        def fmt(match: Match[str]) -> str:
            content = match.group(2)
            if self.doc_inline_code_mode == "bold":
                return colored(content, style="bold")
            return content

        text = re.sub(r"(`{1,2})([^`]+?)\1", fmt, text)
        return text

    def format_description(self, description: str) -> str:
        return self._format_doc_text(description)

    def get_help_for_parameter(
        self,
        param: Parameter,
        flags: tuple[str, ...] | None = None,
    ) -> str:
        if flags is not None and self._use_template_layout():
            return self.format_parameter(param, flags)

        # legacy behavior
        if param.is_required and not param.is_typed:
            return ""
        parts: list[str] = []

        if param.type is bool:
            if param.description is not None:
                description = self._format_doc_text(param.description)
                if not description.endswith((".", "?", "!")):
                    description = description + "."
                parts.append(f"{with_style(description, self.style.description)}")
        else:
            if param.description is not None:
                parts.append(
                    f"{with_style(self._format_doc_text(param.description), self.style.description)} "
                )
            parts.append(self._get_param_extra_help(param))

        text = "".join(parts)
        if param.is_required:
            if self.required_indicator_pos == "left":
                text = f"{self.required_indicator} {text}"
            else:
                text = f"{text} {self.required_indicator}"
        return text

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
        return f"{name_column} {with_style(description, self.style.description)}"

    def get_help_for_class(self, command: Class) -> str:
        ljust = self._get_ljust(command.methods)  # type: ignore
        lines = [self.commands_title]
        for method in command.methods:
            if method.name in self.command_skips:
                continue
            method_name = self.flag_generator.command_translator.translate(method.name)
            lines.append(self.get_command_description(method, ljust, method_name))
        return "\n".join(lines)

    def format_parameter(self, param: Parameter, flags: tuple[str, ...]) -> str:
        _, _, _, is_option = self._build_flag_parts(param, flags)
        template = self.format_option if is_option else self.format_positional
        if not template:
            return HelpLayout.get_help_for_parameter(self, param, None)

        values = self._build_values(param, flags)

        DESC_TOKEN = "<<__DESC__>>"
        probe_vals = dict(values)
        probe_vals["description"] = DESC_TOKEN
        try:
            probe_render = template.format(**probe_vals)
            token_idx = probe_render.find(DESC_TOKEN)
        except Exception:
            probe_render = ""
            token_idx = -1

        if token_idx != -1:
            prefix_str = probe_render[:token_idx]
            prefix_width = ansi_len(prefix_str)

            try:
                term_width = os.get_terminal_size().columns
            except (OSError, AttributeError):
                term_width = 80

            indent_len = 2  # argparse adds a fixed two-space indent for each help line
            wrap_width = max(10, term_width - indent_len - prefix_width)

            raw_desc = self._format_doc_text(param.description or "")

            wrapped: list[str] = []
            for word in raw_desc.split():
                if not wrapped:
                    wrapped.append(word)
                else:
                    if len(wrapped[-1]) + 1 + len(word) <= wrap_width:
                        wrapped[-1] = f"{wrapped[-1]} {word}"
                    else:
                        wrapped.append(word)

            if wrapped:
                cont_indent = " " * prefix_width
                styled_lines = [with_style(wrapped[0], self.style.description)]
                if len(wrapped) > 1:
                    styled_lines.extend(
                        [
                            cont_indent + with_style(line, self.style.description)
                            for line in wrapped[1:]
                        ]
                    )
                values["description"] = "\n".join(styled_lines)

        try:
            rendered = template.format(**values)
        except Exception:
            rendered = f"{values['flag']:<40} {values['description']} {values.get('extra', '')}"

        if param.is_required and values.get("required") and values["required"] not in rendered:
            rendered = f"{rendered} {values['required']}"

        if "[type:" in rendered and "type" in values and not values["type"]:
            rendered = re.sub(r"\s*\[type:\s*\]", "", rendered)
        if not self.include_metavar_in_flag_display:
            rendered = re.sub(r"(\-\w+)\s+[A-Z][A-Z0-9_-]*", r"\1", rendered)
            rendered = re.sub(
                r"(\-\-[A-Za-z0-9][A-Za-z0-9\-]*)\s+[A-Z][A-Z0-9_-]*", r"\1", rendered
            )

        return f"{self.PRE_FMT_PREFIX}{rendered}"

    def get_help_for_multiple_commands(self, commands: dict[str, "Command"]) -> str:
        display_names = [
            self._format_command_display_name(cmd.cli_name, cmd.aliases)
            for cmd in commands.values()
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

    def _use_template_layout(self) -> bool:
        match self.layout_mode:
            case "template":
                return True
            case "adaptive":
                return False
        has_templates = bool(self.format_option or self.format_positional)
        return has_templates

    def _get_ljust(self, commands: list[Class | Function | Method]) -> int:
        return max(self.min_ljust, max([len(i.name) for i in commands]))

    def _get_param_extra_help(self, param: Parameter) -> str:
        parts: list[str] = []
        default_added = False
        if param.is_typed and param.type is not bool:
            if choices := get_choices(param.type):
                param_info = with_style(self.prefix_choices, self.style.extra_data) + ", ".join(
                    [with_style(i, self.style.string) for i in choices]
                )
                if not param.is_required:
                    default_text = with_style(
                        self.prefix_default, self.style.extra_data
                    ) + with_style(str(param.default), self.style.default)
                    param_info += ", " + default_text
                    default_added = True
            else:
                type_str = format_type_for_help(param.type, self.style.type)
                param_info = with_style(self.prefix_type, self.style.extra_data) + type_str

            parts.append(param_info)

        if (
            param.is_optional
            and param.default is not None
            and param.type is not bool
            and not default_added
        ):
            parts.append(", ")
            parts.append(
                with_style(self.prefix_default, self.style.extra_data)
                + with_style(str(param.default), self.style.default)
            )

        if not parts:
            return ""

        return f"[{''.join(parts)}]"

    def _format_command_display_name(self, name: str, aliases: tuple[str, ...] = ()) -> str:
        if not aliases:
            return name
        alias_text = ", ".join(aliases)
        return f"{name} ({alias_text})"

    def _get_primary_boolean_flag(self, param: Parameter, flags: tuple[str, ...]) -> str:
        """
        Determine the primary boolean flag to display based on the default value.

        For boolean parameters, show the flag that represents the "action" to take:
        - If default is True, show --no-flag
        - If default is False or None, show --flag
        """
        longs = [f for f in flags if f.startswith("--")]
        if not longs:
            return flags[0] if flags else ""

        base_flag = None
        no_flag = None

        for flag in longs:
            if flag.startswith("--no-"):
                no_flag = flag
            else:
                base_flag = flag

        if base_flag and not no_flag:
            no_flag = f"--no-{base_flag[2:]}"

        default_value = param.default if param.has_default else False

        if default_value is True and no_flag:
            return no_flag

        return base_flag or longs[0]

    def _build_flag_parts(
        self, param: Parameter, flags: tuple[str, ...]
    ) -> tuple[str, str, str, bool]:
        shorts = [f for f in flags if f.startswith("-") and not f.startswith("--")]
        longs = [f for f in flags if f.startswith("--")]
        is_option = any(f.startswith("-") for f in flags)

        metavar = ""
        needs_value = param.is_typed and param.type is not bool
        if is_option:
            if needs_value and self.include_metavar_in_flag_display:
                metavar = (param.name or "value").upper()
        else:  # Always show uppercase name for positional arguments
            metavar = (param.name or "value").upper()

        def with_metavar(flag: str) -> str:
            return f"{flag} {metavar}" if metavar else flag

        is_bool_param = param.is_typed and param.type is bool
        if is_bool_param:
            primary_flag = self._get_primary_boolean_flag(param, flags)
            flag_short = shorts[0] if shorts else ""
            flag_long = primary_flag
            if flag_short:
                joined = f"{flag_short}, {flag_long}"
            else:
                joined = flag_long
            return joined, flag_short, flag_long, is_option

        flag_short = with_metavar(shorts[0]) if shorts else ""
        flag_long = with_metavar(longs[0]) if longs else ""

        if is_option:
            joined = ", ".join([p for p in (flag_short, flag_long) if p])
        else:
            joined = metavar or (param.name or "")

        return joined, flag_short, flag_long, is_option

    def _build_extra(self, param: Parameter) -> str:
        return HelpLayout._get_param_extra_help(self, param)

    def _build_styled_columns(
        self, flag_short: str, flag_long: str, flag: str, is_option: bool
    ) -> dict[str, str]:
        """
        Build styled flag strings with proper column padding.
        Accounts for ANSI color codes when calculating padding.
        """
        styled_values = {}

        styled_values["flag_short_styled"] = (
            with_style(flag_short, self.style.flag_short) if flag_short else ""
        )
        styled_values["flag_long_styled"] = (
            with_style(flag_long, self.style.flag_long) if flag_long else ""
        )

        if not is_option and flag:
            styled_values["flag_styled"] = with_style(flag, self.style.flag_positional)
        else:
            styled_parts = [
                p
                for p in (styled_values["flag_short_styled"], styled_values["flag_long_styled"])
                if p
            ]
            styled_values["flag_styled"] = ", ".join(styled_parts) if styled_parts else flag

        if flag_short:
            fs = styled_values["flag_short_styled"]
            pad = max(0, self.short_flag_width - ansi_len(fs))
            styled_values["flag_short_col"] = f"{fs}{' ' * pad}"
        else:
            styled_values["flag_short_col"] = " " * self.short_flag_width

        if flag_long:
            fl = styled_values["flag_long_styled"]
            pad = max(0, self.long_flag_width - ansi_len(fl))
            styled_values["flag_long_col"] = f"{fl}{' ' * pad}"
        else:
            styled_values["flag_long_col"] = " " * self.long_flag_width

        if flag:
            fp = styled_values["flag_styled"]
            pad = max(0, self.pos_flag_width - ansi_len(fp))
            styled_values["flag_col"] = f"{fp}{' ' * pad}"
        else:
            styled_values["flag_col"] = " " * self.pos_flag_width

        return styled_values

    def _build_values(self, param: Parameter, flags: tuple[str, ...]) -> dict[str, str]:
        flag, flag_short, flag_long, is_option = self._build_flag_parts(param, flags)

        description = self._format_doc_text(param.description or "")
        if description and not description.endswith((".", "?", "!")) and param.type is bool:
            description += "."
        description = with_style(description, self.style.description)

        default_raw = ""
        if param.type is bool:
            val = param.default if param.has_default else False
            default_raw = "true" if bool(val) else "false"
        elif not param.is_required and param.default is not None:
            default_raw = str(param.default)

        styled_default = with_style(default_raw, self.style.default) if default_raw else ""
        pad = max(0, self.default_field_width - ansi_len(styled_default))
        default_padded = f"{' ' * pad}{styled_default}"
        default = styled_default

        choices = get_choices(param.type) if param.is_typed else None
        choices_str = ""
        if choices:
            choices_str = ", ".join([with_style(str(i), self.style.string) for i in choices])
        choices_label = with_style("choices:", self.style.extra_data) if choices_str else ""
        choices_block = " [" + choices_label + " " + choices_str + "]" if choices_str else ""

        if param.is_typed and param.type is not bool and not choices:
            type_str = format_type_for_help(param.type, self.style.type)
        else:  # Hide type when choices are shown
            type_str = ""

        values: dict[str, str] = {
            "flag": flag,
            "flag_short": flag_short,
            "flag_long": flag_long,
            "description": description,
            "type": type_str,
            "default": default,
            "default_padded": default_padded,
            "choices": choices_str,
            "choices_label": choices_label,
            "choices_block": choices_block,
            "extra": self._build_extra(param),
            "required": self.required_indicator if param.is_required else "",
            "metavar": (param.name or "value").upper(),
        }

        values.update(self._build_styled_columns(flag_short, flag_long, flag, is_option))

        return values


class InterfacyLayout(HelpLayout):
    """Default Interfacy layout"""

    pos_flag_width: int = 24

    format_option = "{flag_col}{description} {extra}"
    format_positional = "{flag_col}{description}"
    include_metavar_in_flag_display = False
    layout_mode = "template"
    required_indicator: str = "(" + colored("*", color="red") + ")"


__all__ = [
    "InterfacyColors",
    "HelpLayout",
    "InterfacyLayout",
]

from inspect import Parameter as StdParameter
from typing import TYPE_CHECKING, ClassVar, Literal

from objinspect import Class, Function, Method, Parameter
from stdl.st import TextStyle, ansi_len, colored, with_style

from interfacy.appearance.colors import ClapColors, NoColor
from interfacy.appearance.layout import HelpLayout
from interfacy.util import format_default_for_help, get_param_choices

if TYPE_CHECKING:
    from interfacy.schema.schema import Command


class InterfacyLayout(HelpLayout):
    """Default Interfacy layout"""

    pos_flag_width: int = 24

    column_gap: str = "    "
    format_option = "{flag_col}{column_gap}{description}{extra}"
    format_positional = "{flag_col}{column_gap}{description}"
    include_metavar_in_flag_display = False
    layout_mode = "template"
    required_indicator: str = "(" + colored("*", color="red") + ")"

    def _build_values(self, param: Parameter, flags: tuple[str, ...]) -> dict[str, str]:
        values = super()._build_values(param, flags)
        values["column_gap"] = self.column_gap
        extra = values.get("extra", "")
        values["extra"] = f" {extra}" if extra else ""
        return values


class Aligned(InterfacyLayout):
    short_flag_width: int = 6
    long_flag_width: int = 18
    pos_flag_width: int = 24
    default_field_width_max: int = 12
    default_overflow_mode: Literal["inline", "newline"] = "inline"
    suppress_empty_default_brackets_for_help: ClassVar[bool] = True

    format_option = "{flag_short_col}{flag_long_col}[{default_padded}] {description}{choices_block}"
    format_positional = "{flag_col}{description}{choices_block}"
    include_metavar_in_flag_display = False
    layout_mode = "template"


class AlignedTyped(InterfacyLayout):
    short_flag_width: int = 6
    long_flag_width: int = 18
    pos_flag_width: int = 24
    default_field_width_max: int = 12
    default_overflow_mode: Literal["inline", "newline"] = "inline"
    suppress_empty_default_brackets_for_help: ClassVar[bool] = True

    format_option = "{flag_short_col}{flag_long_col}[{default_padded}] {description} [type: {type}]{choices_block}"
    format_positional = "{flag_col}{description} [type: {type}]{choices_block}"
    include_metavar_in_flag_display = False
    layout_mode = "template"


class Modern(InterfacyLayout):
    include_metavar_in_flag_display = False
    default_field_width = 8
    default_label_for_help = "default"

    short_flag_width: int = 6
    long_flag_width: int = 18
    pos_flag_width: int = 24

    format_option = "{flag_short_col}{flag_long_col}  {description}{details}"
    format_positional = "{flag_col} {description}{details}"
    layout_mode = "template"

    def _build_values(self, param: Parameter, flags: tuple[str, ...]) -> dict[str, str]:  # type: ignore[override]
        values = super()._build_values(param, flags)

        detail_parts: list[str] = []
        if values.get("default"):
            detail_parts.append("default: " + values["default"])

        if values.get("type"):
            detail_parts.append("type: " + values["type"])

        if values.get("choices"):
            detail_parts.append("choices: " + values["choices"])

        if detail_parts:
            is_option = bool(values.get("flag_short") or values.get("flag_long"))
            if is_option:
                pad_count = self.short_flag_width + self.long_flag_width + 2
            else:
                pad_count = self.pos_flag_width + 2

            arrow = with_style("↳", self.style.extra_data)
            details_text = with_style(" | ", self.style.extra_data).join(detail_parts)
            raw_desc = self._format_doc_text(param.description or "")
            if not raw_desc.strip():
                inline_arrow = with_style("→", self.style.extra_data)
                values["details"] = f"{inline_arrow} {details_text}"
            else:
                values["details"] = "\n" + (" " * pad_count) + f"{arrow} " + details_text
        else:
            values["details"] = ""

        return values


class ClapLayout(HelpLayout):
    """Layout that mimics clap's default help output."""

    style = ClapColors()

    usage_prefix: str = "Usage: "
    section_title_map: ClassVar[dict[str, str]] = {
        "positional arguments": "Arguments",
        "optional arguments": "Options",
        "options": "Options",
        "subcommands": "Commands",
        "commands": "Commands",
        "commands:": "Commands",
    }
    section_heading_style = TextStyle(color="green", style="bold")
    usage_style = TextStyle(color="green", style="bold")
    usage_text_style = TextStyle(color="cyan", style="bold")
    placeholder_style = TextStyle(color="cyan", style="bold")
    command_name_style = TextStyle(color="cyan", style="bold")
    use_action_extra: ClassVar[bool] = True
    choices_label_text: ClassVar[str] = "possible values:"
    default_label_text: ClassVar[str] = "default:"
    dashify_metavar: ClassVar[bool] = True

    commands_title: str = "Commands:"
    required_indicator: str = ""
    enable_required_indicator: bool = False
    include_metavar_in_flag_display: bool = True
    clear_metavar: bool = False
    doc_inline_code_mode: Literal["bold", "strip"] = "strip"

    pos_flag_width: int = 26
    column_gap: ClassVar[str] = "  "
    no_description_gap: ClassVar[str] = "  "
    collapse_gap_when_no_description: ClassVar[bool] = False
    format_option = "{flag_col}{column_gap}{description}{extra}"
    format_positional = "{flag_col}{column_gap}{description}{extra}"
    layout_mode = "template"

    def _format_metavar(self, name: str, *, is_varargs: bool) -> str:
        text = name.upper()
        if self.dashify_metavar:
            text = text.replace("_", "-")
        if is_varargs:
            text = f"{text}..."
        return f"<{text}>"

    def _build_flag_parts(
        self, param: Parameter, flags: tuple[str, ...]
    ) -> tuple[str, str, str, bool]:
        shorts = [f for f in flags if f.startswith("-") and not f.startswith("--")]
        longs = [f for f in flags if f.startswith("--")]
        is_option = any(f.startswith("-") for f in flags)

        metavar = ""
        needs_value = param.is_typed and not self._param_is_bool(param)
        is_varargs = param.kind == StdParameter.VAR_POSITIONAL
        if is_option:
            if needs_value and self.include_metavar_in_flag_display:
                metavar = self._format_metavar(param.name or "value", is_varargs=is_varargs)
        else:
            metavar = self._format_metavar(param.name or "value", is_varargs=is_varargs)

        is_bool_param = param.is_typed and self._param_is_bool(param)
        if is_bool_param:
            primary_flag = self._get_primary_boolean_flag(param, flags)
            flag_short = shorts[0] if shorts else ""
            flag_long = primary_flag
            if flag_short:
                joined = f"{flag_short}, {flag_long}"
            else:
                joined = flag_long
            return joined, flag_short, flag_long, is_option

        flag_short = shorts[0] if shorts else ""
        flag_long = longs[0] if longs else ""

        if metavar:
            if flag_long:
                flag_long = f"{flag_long} {metavar}"
            elif flag_short:
                flag_short = f"{flag_short} {metavar}"

        if is_option:
            joined = ", ".join([p for p in (flag_short, flag_long) if p])
        else:
            joined = metavar or (param.name or "")

        return joined, flag_short, flag_long, is_option

    def _build_extra(self, param: Parameter) -> str:
        parts: list[str] = []

        if not self._param_is_bool(param):
            if not param.is_required and param.default is not None:
                label = with_style("default:", self.style.extra_data)
                value = with_style(format_default_for_help(param.default), self.style.default)
                parts.append(f"[{label} {value}]")

            if param.is_typed:
                choices = get_param_choices(param, for_display=True)
                if choices:
                    label = "possible values:"
                    values = ", ".join([with_style(str(i), self.style.string) for i in choices])
                    parts.append(f"[{label} {values}]")

        if not parts:
            return ""

        return " " + " ".join(parts)

    def _style_flag_token(self, flag: str, style: TextStyle) -> str:
        if not flag:
            return ""
        if " " not in flag:
            return with_style(flag, style)
        head, tail = flag.split(" ", 1)
        return f"{with_style(head, style)} {with_style(tail, self.placeholder_style)}"

    def _build_styled_columns(
        self, flag_short: str, flag_long: str, flag: str, is_option: bool
    ) -> dict[str, str]:
        styled_values: dict[str, str] = {}

        styled_values["flag_short_styled"] = (
            self._style_flag_token(flag_short, self.style.flag_short) if flag_short else ""
        )
        styled_values["flag_long_styled"] = (
            self._style_flag_token(flag_long, self.style.flag_long) if flag_long else ""
        )

        if not is_option and flag:
            styled_values["flag_styled"] = self._style_flag_token(flag, self.style.flag_positional)
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
        values = super()._build_values(param, flags)
        desc = values.get("description", "")
        extra = values.get("extra", "")
        if not desc.strip() and extra.startswith(" "):
            extra = extra[1:]

        if self.collapse_gap_when_no_description and not desc.strip():
            values["column_gap"] = self.no_description_gap if extra else ""
        else:
            values["column_gap"] = self.column_gap
        values["extra"] = extra
        return values

    def get_command_description(
        self,
        command: Class | Function | Method,
        ljust: int,
        name: str | None = None,
        aliases: tuple[str, ...] = (),
    ) -> str:  # type: ignore[override]
        name = name or command.name
        command_name = self._format_command_display_name(name, aliases)
        name_styled = with_style(command_name, self.style.flag_long)
        pad = max(0, ljust - len(command_name) - 3)
        name_column = f"   {name_styled}{' ' * pad}"
        description = command.description or ""
        return f"{name_column} {with_style(description, self.style.description)}"

    def _format_commands_title(self) -> str:
        heading_style = getattr(self, "section_heading_style", None)
        if heading_style is not None:
            return with_style(self.commands_title, heading_style)
        return self.commands_title

    def get_help_for_class(self, command: Class) -> str:  # type: ignore[override]
        display_names: list[str] = []
        for method in command.methods:
            if method.name in self.command_skips:
                continue
            method_name = self.flag_generator.command_translator.translate(method.name)
            display_names.append(self._format_command_display_name(method_name, ()))

        max_display = max([len(name) for name in display_names], default=0)
        ljust = self.get_commands_ljust(max_display)
        lines = [self._format_commands_title()]
        for method in command.methods:
            if method.name in self.command_skips:
                continue
            method_name = self.flag_generator.command_translator.translate(method.name)
            lines.append(self.get_command_description(method, ljust, method_name))
        return "\n".join(lines)

    def get_help_for_multiple_commands(self, commands: dict[str, "Command"]) -> str:  # type: ignore[override]
        display_names = [
            self._format_command_display_name(cmd.cli_name, cmd.aliases)
            for cmd in commands.values()
        ]
        max_display = max([len(name) for name in display_names], default=0)
        ljust = self.get_commands_ljust(max_display)
        lines = [self._format_commands_title()]
        for name, command in commands.items():
            if command.obj is None:
                command_name = self._format_command_display_name(name, command.aliases)
                name_column = f"   {command_name}".ljust(ljust)
                description = command.raw_description or ""
                lines.append(f"{name_column} {with_style(description, self.style.description)}")
            else:
                lines.append(
                    self.get_command_description(
                        command.obj,
                        ljust,
                        name,
                        command.aliases,
                    )
                )
        return "\n".join(lines)


class ArgparseLayout(HelpLayout):
    """Layout that follows the default ``argparse`` help output."""

    style = NoColor()

    include_metavar_in_flag_display = True
    required_indicator: str = ""
    enable_required_indicator: bool = False
    default_label_for_help: str = ""
    clear_metavar: bool = False

    help_position: int = 28  # type:ignore
    layout_mode: Literal["auto", "adaptive", "template"] = "adaptive"

    def get_help_for_parameter(
        self,
        param: Parameter,
        flags: tuple[str, ...] | None = None,
    ) -> str:
        description = self.format_description(param.description or "")
        if param.has_default:
            if len(description):
                description += ". "
            description += f"Defaults to {param.default}."
        return description


__all__ = [
    "ClapLayout",
    "ArgparseLayout",
    "Aligned",
    "AlignedTyped",
    "Modern",
    "InterfacyLayout",
]

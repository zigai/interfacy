import argparse
from collections.abc import Sequence
from inspect import Parameter as StdParameter
from typing import TYPE_CHECKING, ClassVar, Literal

from objinspect import Class, Function, Method, Parameter
from stdl.st import TextStyle, ansi_len, colored, with_style

from interfacy.appearance.colors import ClapColors, NoColor
from interfacy.appearance.layout import HelpLayout
from interfacy.util import format_default_for_help, get_param_choices

if TYPE_CHECKING:
    from interfacy.schema.schema import Argument, Command


class InterfacyLayout(HelpLayout):
    """Default Interfacy layout."""

    pos_flag_width: int = 24

    column_gap: str = "    "
    format_option = "{flag_col}{column_gap}{description}{extra}"
    format_positional = "{flag_col}{column_gap}{description}"
    include_metavar_in_flag_display = False
    layout_mode = "template"
    required_indicator: str = "(" + colored("*", color="red") + ")"

    def _apply_interfacy_columns(self, values: dict[str, str]) -> dict[str, str]:
        values["column_gap"] = self.column_gap
        extra = values.get("extra", "")
        description = values.get("description", "")
        has_visible_description = ansi_len(description) > 0
        if extra:
            values["extra"] = f" {extra}" if has_visible_description else extra
        else:
            values["extra"] = ""
        return values

    def _build_values(self, param: Parameter, flags: tuple[str, ...]) -> dict[str, str]:
        return self._apply_interfacy_columns(super()._build_values(param, flags))

    def _build_values_from_argument(self, arg: "Argument") -> dict[str, str]:
        return self._apply_interfacy_columns(super()._build_values_from_argument(arg))


class Aligned(InterfacyLayout):
    """Layout with aligned default column and compact flag spacing."""

    short_flag_width: int = 6
    long_flag_width: int = 18
    pos_flag_width: int = 24
    default_field_width_max: int = 12
    default_overflow_mode: Literal["inline", "newline"] = "inline"
    suppress_empty_default_brackets_for_help: bool = True

    format_option = "{flag_short_col}{flag_long_col}[{default_padded}] {description}{choices_block}"
    format_positional = "{flag_col}{description}{choices_block}"
    include_metavar_in_flag_display = False
    layout_mode = "template"

    def get_commands_ljust(self, max_display_len: int) -> int:
        base = max(self.min_ljust, max_display_len + 3)
        default_idx = self._get_template_token_index("default_padded")
        if default_idx is not None:
            return max(base, default_idx + 1)
        prefix_len = self._get_commands_prefix_len()
        if prefix_len is not None:
            return max(base, prefix_len + 1)
        return super().get_commands_ljust(max_display_len)


class AlignedTyped(InterfacyLayout):
    """Aligned layout that includes explicit type display."""

    short_flag_width: int = 6
    long_flag_width: int = 18
    pos_flag_width: int = 24
    default_field_width_max: int = 12
    default_overflow_mode: Literal["inline", "newline"] = "inline"
    suppress_empty_default_brackets_for_help: bool = True

    format_option = "{flag_short_col}{flag_long_col}[{default_padded}] {description} [type: {type}]{choices_block}"
    format_positional = "{flag_col}{description} [type: {type}]{choices_block}"
    include_metavar_in_flag_display = False
    layout_mode = "template"

    def get_commands_ljust(self, max_display_len: int) -> int:
        base = max(self.min_ljust, max_display_len + 3)
        default_idx = self._get_template_token_index("default_padded")
        if default_idx is not None:
            return max(base, default_idx + 1)
        prefix_len = self._get_commands_prefix_len()
        if prefix_len is not None:
            return max(base, prefix_len + 1)
        return super().get_commands_ljust(max_display_len)


class Modern(InterfacyLayout):
    """Modern layout with inline detail rows for defaults and types."""

    include_metavar_in_flag_display = False
    default_field_width = 8
    default_label_for_help = "default"

    short_flag_width: int = 6
    long_flag_width: int = 18
    pos_flag_width: int = 24

    format_option = "{flag_short_col}{flag_long_col}  {description}{details}"
    format_positional = "{flag_col} {description}{details}"
    layout_mode = "template"

    def _with_details(self, values: dict[str, str], raw_description: str) -> dict[str, str]:
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
            if not raw_description.strip():
                inline_arrow = with_style("→", self.style.extra_data)
                values["details"] = f"{inline_arrow} {details_text}"
            else:
                values["details"] = "\n" + (" " * pad_count) + f"{arrow} " + details_text
        else:
            values["details"] = ""

        return values

    def _build_values(self, param: Parameter, flags: tuple[str, ...]) -> dict[str, str]:
        values = super()._build_values(param, flags)
        return self._with_details(values, self._format_doc_text(param.description or ""))

    def _build_values_from_argument(self, arg: "Argument") -> dict[str, str]:
        values = super()._build_values_from_argument(arg)
        return self._with_details(values, self._format_doc_text(arg.help or ""))


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
    section_heading_style = TextStyle(color="light_green", style="bold")
    usage_style = TextStyle(color="light_green", style="bold")
    usage_text_style = TextStyle(color="cyan", style="bold")
    placeholder_style = TextStyle(color="cyan", style="bold")
    command_name_style = TextStyle(color="cyan", style="bold")
    help_option_description: str = "Print help"
    compact_options_usage: bool = True
    parser_command_usage_suffix: str = "[OPTIONS] [COMMAND]"
    subcommand_usage_placeholder: str = "[COMMAND]"
    description_before_usage: bool = True
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

    def format_usage_metavar(self, name: str, *, is_varargs: bool = False) -> str:
        return self._format_metavar(name, is_varargs=is_varargs)

    def _build_flag_parts(
        self, param: Parameter, flags: tuple[str, ...]
    ) -> tuple[str, str, str, bool]:
        is_option = any(flag.startswith("-") for flag in flags)
        is_bool = param.is_typed and self._param_is_bool(param)
        needs_value = param.is_typed and not is_bool
        is_varargs = param.kind == StdParameter.VAR_POSITIONAL
        return self._build_clap_flag_parts(
            flags=flags,
            is_option=is_option,
            is_bool=is_bool,
            needs_value=needs_value,
            metavar_name=param.name or "value",
            is_varargs=is_varargs,
            primary_bool_flag=self._get_primary_boolean_flag(param, flags),
        )

    def _build_clap_extra(
        self,
        *,
        is_bool: bool,
        is_required: bool,
        has_default: bool,
        default_value: object,
        choices: Sequence[object] | None,
    ) -> str:
        parts: list[str] = []

        if not is_bool:
            if not is_required and has_default:
                label = with_style("default:", self.style.extra_data)
                value = with_style(format_default_for_help(default_value), self.style.default)
                parts.append(f"[{label} {value}]")

            if choices:
                label = "possible values:"
                values = ", ".join(
                    [
                        with_style(self._format_choice_for_help(i), self.style.string)
                        for i in choices
                    ]
                )
                parts.append(f"[{label} {values}]")

        if not parts:
            return ""
        return " " + " ".join(parts)

    def _build_extra(self, param: Parameter) -> str:
        choices = get_param_choices(param, for_display=True) if param.is_typed else None
        return self._build_clap_extra(
            is_bool=self._param_is_bool(param),
            is_required=param.is_required,
            has_default=param.default is not None,
            default_value=param.default,
            choices=choices,
        )

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
            active_pos_width = max(
                self._get_pos_flag_width_base(),
                getattr(self, "_active_pos_flag_width", self.pos_flag_width),
            )
            pad = max(0, active_pos_width - ansi_len(fp))
            styled_values["flag_col"] = f"{fp}{' ' * pad}"
        else:
            active_pos_width = max(
                self._get_pos_flag_width_base(),
                getattr(self, "_active_pos_flag_width", self.pos_flag_width),
            )
            styled_values["flag_col"] = " " * active_pos_width

        return styled_values

    def _apply_clap_spacing(self, values: dict[str, str]) -> dict[str, str]:
        desc = values.get("description", "")
        extra = values.get("extra", "")
        has_visible_description = ansi_len(desc) > 0

        if not has_visible_description:
            # Metadata-only rows should align to the standard help-text column.
            extra = extra.lstrip()
            values["column_gap"] = self.column_gap if extra else ""
        else:
            values["column_gap"] = self.column_gap
        values["extra"] = extra
        return values

    def _build_values(self, param: Parameter, flags: tuple[str, ...]) -> dict[str, str]:
        values = super()._build_values(param, flags)
        return self._apply_clap_spacing(values)

    def _build_clap_flag_parts(
        self,
        *,
        flags: tuple[str, ...],
        is_option: bool,
        is_bool: bool,
        needs_value: bool,
        metavar_name: str,
        is_varargs: bool,
        primary_bool_flag: str,
    ) -> tuple[str, str, str, bool]:
        shorts = [f for f in flags if f.startswith("-") and not f.startswith("--")]
        longs = [f for f in flags if f.startswith("--")]

        metavar = ""
        if is_option:
            if needs_value and self.include_metavar_in_flag_display:
                metavar = self._format_metavar(metavar_name, is_varargs=is_varargs)
        else:
            metavar = self._format_metavar(metavar_name, is_varargs=is_varargs)

        if is_bool:
            flag_short = shorts[0] if shorts else ""
            flag_long = primary_bool_flag
            joined = f"{flag_short}, {flag_long}" if flag_short else flag_long
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
            joined = metavar or metavar_name

        return joined, flag_short, flag_long, is_option

    def _build_flag_parts_from_argument(self, arg: "Argument") -> tuple[str, str, str, bool]:
        is_option = self._enum_matches(arg.kind, "OPTION")
        is_bool = self._arg_is_bool(arg)
        needs_value = arg.type is not None and not is_bool
        is_varargs = self._enum_matches(arg.value_shape, "LIST") and not is_option
        return self._build_clap_flag_parts(
            flags=arg.flags,
            is_option=is_option,
            is_bool=is_bool,
            needs_value=needs_value,
            metavar_name=arg.metavar or arg.display_name or arg.name or "value",
            is_varargs=is_varargs,
            primary_bool_flag=self._get_primary_boolean_flag_from_argument(arg),
        )

    def _build_extra_from_argument(self, arg: "Argument") -> str:
        choices = (
            tuple(self._format_argument_choice_for_help(arg, i) for i in arg.choices)
            if arg.choices
            else None
        )
        return self._build_clap_extra(
            is_bool=self._arg_is_bool(arg),
            is_required=arg.required,
            has_default=self._arg_has_default(arg),
            default_value=arg.default,
            choices=choices,
        )

    def _build_values_from_argument(self, arg: "Argument") -> dict[str, str]:
        return self._apply_clap_spacing(super()._build_values_from_argument(arg))

    def _format_command_display_name(self, name: str, aliases: tuple[str, ...] = ()) -> str:
        if not aliases:
            return name
        return ", ".join((name, *aliases))

    def get_command_description(
        self,
        command: Class | Function | Method,
        ljust: int,
        name: str | None = None,
        aliases: tuple[str, ...] = (),
    ) -> str:
        """
        Return a styled command description line.

        Args:
            command (Class | Function | Method): Command to describe.
            ljust (int): Column width for the name.
            name (str | None): Override display name.
            aliases (tuple[str, ...]): Alternate CLI names.
        """
        name = name or command.name
        command_name = self._format_command_display_name(name, aliases)
        name_styled = with_style(command_name, self.style.flag_long)
        pad = max(0, ljust - len(command_name) - 3)
        name_column = f"   {name_styled}{' ' * pad}"
        description = command.description or ""
        return f"{name_column} {with_style(description, self.style.description)}"

    def _format_commands_title(self) -> str:
        if self.section_heading_style is not None:
            return with_style(self.commands_title, self.section_heading_style)
        return self.commands_title

    def get_help_for_class(self, command: Class) -> str:
        """
        Build help text for class subcommands with styled headings.

        Args:
            command (Class): Inspected class command.
        """
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

    def get_help_for_multiple_commands(self, commands: dict[str, "Command"]) -> str:
        """
        Build a styled command listing for multiple commands.

        Args:
            commands (dict[str, Command]): Command map keyed by name.
        """
        display_names = [
            self._format_command_display_name(cmd.cli_name, cmd.aliases)
            for cmd in commands.values()
        ]
        max_display = max([len(name) for name in display_names], default=0)
        ljust = self.get_commands_ljust(max_display)
        lines = [self._format_commands_title()]
        for command in commands.values():
            cli_name = command.cli_name
            if command.obj is None:
                command_name = self._format_command_display_name(cli_name, command.aliases)
                name_styled = with_style(command_name, self.style.flag_long)
                pad = max(0, ljust - len(command_name) - 3)
                name_column = f"   {name_styled}{' ' * pad}"
                description = command.raw_description or ""
                lines.append(f"{name_column} {with_style(description, self.style.description)}")
            else:
                lines.append(
                    self.get_command_description(
                        command.obj,
                        ljust,
                        cli_name,
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

    help_position: int = 32
    layout_mode: Literal["auto", "adaptive", "template"] = "adaptive"

    @staticmethod
    def _with_default_sentence(description: str, has_default: bool, default: object) -> str:
        if has_default:
            if description:
                description += ". "
            description += f"Defaults to {format_default_for_help(default)}."
        return description

    def get_help_for_parameter(
        self,
        param: Parameter,
        flags: tuple[str, ...] | None = None,  # noqa: ARG002 - API compatibility
    ) -> str:
        """
        Return help text following argparse's default style.

        Args:
            param (Parameter): Parameter metadata.
            flags (tuple[str, ...] | None): CLI flags for display.
        """
        description = self.format_description(param.description or "")
        has_default = param.has_default and param.default is not None and not param.is_required
        return self._with_default_sentence(description, has_default, param.default)

    def format_argument(
        self,
        arg: "Argument",
        indent: int = 2,  # noqa: ARG002 - API compatibility
    ) -> str:
        description = self.format_description(arg.help or "")
        has_default = (
            not arg.required and arg.default is not argparse.SUPPRESS and arg.default is not None
        )
        return self._with_default_sentence(description, has_default, arg.default)


__all__ = [
    "Aligned",
    "AlignedTyped",
    "ArgparseLayout",
    "ClapLayout",
    "InterfacyLayout",
    "Modern",
]

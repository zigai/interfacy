from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from stdl.st import TextStyle, ansi_len, with_style

from interfacy.help.colors import ClapColors
from interfacy.help.formatting import format_default_for_help
from interfacy.help.layouts.base import HelpLayout
from interfacy.help.style import HelpStyle

if TYPE_CHECKING:  # pragma: no cover
    from interfacy.schema import Argument


@dataclass(kw_only=True)
class ClapLayout(HelpLayout):
    """Layout that mimics clap's default help output."""

    style: HelpStyle = field(default_factory=ClapColors)

    usage_prefix: str | None = "Usage: "
    section_title_map: dict[str, str] | None = field(
        default_factory=lambda: {
            "positional arguments": "Arguments",
            "optional arguments": "Options",
            "options": "Options",
            "subcommands": "Commands",
            "commands": "Commands",
            "commands:": "Commands",
        }
    )
    help_option_description: str = "Print help"
    compact_options_usage: bool = True
    parser_command_usage_suffix: str = "[OPTIONS] [COMMAND]"
    subcommand_usage_placeholder: str = "[COMMAND]"
    description_before_usage: bool = True
    choices_label_text: str = "possible values:"
    default_label_text: str = "default:"
    dashify_metavar: bool = True

    commands_title: str = "Commands:"
    required_indicator: str = ""
    include_metavar_in_flag_display: bool = True
    clear_metavar: bool = False
    doc_inline_code_mode: Literal["bold", "strip"] = "strip"

    pos_flag_width: int = 26
    column_gap: str = "  "
    no_description_gap: str = "  "
    collapse_gap_when_no_description: bool = False
    format_option: str | None = "{flag_col}{column_gap}{description}{extra}"
    format_positional: str | None = "{flag_col}{column_gap}{description}{extra}"
    layout_mode: Literal["auto", "adaptive", "template"] = "template"

    def _format_metavar(self, name: str, *, is_varargs: bool) -> str:
        text = name.upper()
        if self.dashify_metavar:
            text = text.replace("_", "-")

        if is_varargs:
            text = f"{text}..."

        return f"<{text}>"

    def format_usage_metavar(self, name: str, *, is_varargs: bool = False) -> str:
        return self._format_metavar(name, is_varargs=is_varargs)

    def _build_clap_extra(
        self,
        *,
        is_bool: bool,
        is_required: bool,
        has_default: bool,
        default_value: Any,
        choices: Sequence[Any] | None,
    ) -> str:
        parts: list[str] = []

        if not is_bool:
            if not is_required and has_default:
                label = with_style(self.default_label_text, self.style.extra_data)
                value = with_style(format_default_for_help(default_value), self.style.default)
                parts.append(f"[{label} {value}]")

            if choices:
                label = self.choices_label_text
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

    def _style_flag_token(self, flag: str, style: TextStyle) -> str:
        if not flag:
            return ""

        if " " not in flag:
            return with_style(flag, style)

        head, tail = flag.split(" ", 1)

        placeholder_style = self.style.placeholder_style or self.style.flag_long

        return f"{with_style(head, style)} {with_style(tail, placeholder_style)}"

    def _apply_clap_spacing(self, values: dict[str, str]) -> dict[str, str]:
        desc = values.get("description", "")
        extra = values.get("extra", "")
        has_visible_description = ansi_len(desc) > 0

        if not has_visible_description:
            # Metadata-only rows should align to the standard help-text column.
            extra = extra.lstrip()
            if extra:
                if self.collapse_gap_when_no_description:
                    values["column_gap"] = self.no_description_gap
                else:
                    values["column_gap"] = self.column_gap
            else:
                values["column_gap"] = ""
        else:
            values["column_gap"] = self.column_gap

        values["extra"] = extra

        return values

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
            default_value=arg.argument_default.value,
            choices=choices,
        )

    def _build_values_from_argument(self, arg: "Argument") -> dict[str, str]:
        return self._apply_clap_spacing(super()._build_values_from_argument(arg))

    def _format_command_display_name(self, name: str, aliases: tuple[str, ...] = ()) -> str:
        if not aliases:
            return name

        return ", ".join((name, *aliases))

    def _format_commands_title(self) -> str:
        if self.style.section_heading_style is not None:
            return with_style(self.commands_title, self.style.section_heading_style)

        return self.commands_title

    def _format_command_name_for_help(self, command_name: str) -> str:
        return with_style(command_name, self.style.command_name_style or self.style.flag_long)


__all__ = [
    "ClapLayout",
]

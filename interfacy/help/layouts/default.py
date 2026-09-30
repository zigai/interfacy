from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from stdl.st import ansi_len, colored, with_style

from interfacy.help.formatting import format_default_for_help, format_type_for_help
from interfacy.help.layouts.base import HelpLayout

if TYPE_CHECKING:  # pragma: no cover
    from interfacy.schema import Argument


@dataclass(kw_only=True)
class InterfacyLayout(HelpLayout):
    """Interfacy-branded template layout."""

    pos_flag_width: int = 24

    column_gap: str = "    "
    format_option: str | None = "{flag_col}{column_gap}{description}{extra}"
    format_positional: str | None = "{flag_col}{column_gap}{description}{extra}"
    include_metavar_in_flag_display: bool = False
    layout_mode: Literal["auto", "adaptive", "template"] = "template"
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

    def _build_values_from_argument(self, arg: "Argument") -> dict[str, str]:
        return self._apply_interfacy_columns(super()._build_values_from_argument(arg))

    def _build_extra_from_argument(self, arg: "Argument") -> str:
        parts: list[str] = []
        default_added = False
        is_typed = arg.type is not None
        is_bool = self._arg_is_bool(arg)

        if is_typed and not is_bool:
            if arg.choices:
                param_info = self.prefix_choices + ", ".join(
                    [
                        with_style(self._format_argument_choice_for_help(arg, i), self.style.string)
                        for i in arg.choices
                    ]
                )
                if not arg.required and self._arg_has_default(arg):
                    default_text = self.prefix_default + with_style(
                        format_default_for_help(arg.argument_default.value), self.style.default
                    )
                    param_info += ", " + default_text
                    default_added = True
                parts.append(param_info)
            else:
                if not arg.required and self._arg_has_default(arg):
                    parts.append(
                        self.prefix_default
                        + with_style(
                            format_default_for_help(arg.argument_default.value),
                            self.style.default,
                        )
                    )
                    default_added = True
                type_str = format_type_for_help(
                    self._type_for_argument_help(arg), self.style.type, theme=self.style
                )
                parts.append(self.prefix_type + type_str)

        if not arg.required and self._arg_has_default(arg) and not is_bool and not default_added:
            parts.append(
                self.prefix_default
                + with_style(
                    format_default_for_help(arg.argument_default.value), self.style.default
                )
            )

        if not parts:
            return ""

        return f"[{', '.join(parts)}]"


__all__ = [
    "InterfacyLayout",
]

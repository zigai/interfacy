from typing import Literal

from objinspect import Parameter
from stdl.st import with_style

from interfacy.appearance.colors import NoColor
from interfacy.appearance.layout import HelpLayout, InterfacyLayout


class Aligned(InterfacyLayout):
    short_flag_width: int = 6
    long_flag_width: int = 18
    pos_flag_width: int = 24

    format_option = "{flag_short_col}{flag_long_col}[{default_padded}] {description}{choices_block}"
    format_positional = "{flag_col}{description}{choices_block}"
    include_metavar_in_flag_display = False
    layout_mode = "template"


class AlignedTyped(InterfacyLayout):
    short_flag_width: int = 6
    long_flag_width: int = 18
    pos_flag_width: int = 24

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

    format_option = "{flag_short_col}{flag_long_col} {desc_line}{details}"
    format_positional = "{flag_col} {desc_line}{details}"
    layout_mode = "template"

    def _build_values(self, param: Parameter, flags: tuple[str, ...]) -> dict[str, str]:  # type: ignore[override]
        values = super()._build_values(param, flags)

        desc_line = values.get("description", "")
        if values.get("required"):
            desc_line = f"{desc_line} {values['required']}"
        values["desc_line"] = desc_line

        is_option = bool(values.get("flag_short") or values.get("flag_long"))
        if is_option:
            pad_count = self.short_flag_width + self.long_flag_width + 1 + 2
        else:
            pad_count = self.pos_flag_width + 1 + 2

        detail_parts: list[str] = []
        if values.get("default"):
            detail_parts.append(
                with_style("default:", self.style.extra_data) + " " + values["default"]
            )

        if values.get("type"):
            detail_parts.append(with_style("type:", self.style.extra_data) + " " + values["type"])

        if values.get("choices"):
            detail_parts.append(
                with_style("choices:", self.style.extra_data) + " " + values["choices"]
            )

        if detail_parts:
            arrow = with_style("↳", self.style.extra_data)
            details_text = with_style(" | ", self.style.extra_data).join(detail_parts)
            values["details"] = "\n" + (" " * pad_count) + f"{arrow} " + details_text
        else:
            values["details"] = ""

        return values


class ArgparseLayout(HelpLayout):
    """Layout that follows the default ``argparse`` help output."""

    style = NoColor()

    include_metavar_in_flag_display = True
    required_indicator: str = ""
    enable_required_indicator: bool = False
    default_label_for_help: str = ""
    clear_metavar: bool = False

    help_position: int = 24  # type:ignore
    layout_mode: Literal["auto", "adaptive", "template"] = "adaptive"

    def get_help_for_parameter(
        self,
        param: Parameter,
        flags: tuple[str, ...] | None = None,
    ) -> str:
        description = param.description or ""
        if param.has_default:
            if len(description):
                description += ". "
            description += f"Defaults to {param.default}."
        return description


__all__ = [
    "ArgparseLayout",
    "Aligned",
    "AlignedTyped",
    "Modern",
]

from objinspect import Parameter
from stdl.st import with_style

from interfacy.appearance.layout import InterfacyLayout


class Aligned(InterfacyLayout):
    short_flag_width: int = 6
    long_flag_width: int = 18
    pos_flag_width: int = 24

    format_option = "{flag_short_col}{flag_long_col}[{default_padded}] {description}"
    format_positional = "{flag_col}{description}"
    include_metavar_in_flag_display = False
    layout_mode = "template"


class AlignedTyped(InterfacyLayout):
    short_flag_width: int = 6
    long_flag_width: int = 18
    pos_flag_width: int = 24

    format_option = "{flag_short_col}{flag_long_col}[{default_padded}] {description} [type: {type}]"
    format_positional = "{flag_col}{description} [type: {type}]"
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


__all__ = [
    "Aligned",
    "AlignedTyped",
    "Modern",
]

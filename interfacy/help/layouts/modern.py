from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from stdl.st import with_style

from interfacy.help.layouts.default import InterfacyLayout

if TYPE_CHECKING:  # pragma: no cover
    from interfacy.schema import Argument


@dataclass(kw_only=True)
class Modern(InterfacyLayout):
    """Modern layout with inline detail rows for defaults and types."""

    include_metavar_in_flag_display: bool = False
    default_field_width: int = 8

    short_flag_width: int = 6
    long_flag_width: int = 18
    pos_flag_width: int = 24

    format_option: str | None = "{flag_short_col}{flag_long_col}  {description}{details}"
    format_positional: str | None = "{flag_col} {description}{details}"
    layout_mode: Literal["auto", "adaptive", "template"] = "template"

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

    def _build_values_from_argument(self, arg: "Argument") -> dict[str, str]:
        values = super()._build_values_from_argument(arg)
        return self._with_details(values, self._format_doc_text(arg.help or ""))


__all__ = [
    "Modern",
]

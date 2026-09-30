from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from stdl.st import ansi_len

from interfacy.common.terminal import strip_ansi
from interfacy.help.layouts.default import InterfacyLayout

if TYPE_CHECKING:  # pragma: no cover
    from interfacy.schema import Argument


@dataclass(kw_only=True)
class AlignedLayoutBase(InterfacyLayout):
    """Shared column and help-slot policy for the aligned preset family."""

    short_flag_width: int = 6
    long_flag_width: int = 18
    pos_flag_width: int = 24
    default_field_width_max: int | None = 12
    default_overflow_mode: Literal["inline", "newline"] = "inline"
    suppress_empty_default_brackets_for_help: bool = True
    keep_empty_default_slot_for_help: bool = True

    include_metavar_in_flag_display: bool = False
    layout_mode: Literal["auto", "adaptive", "template"] = "template"

    def get_commands_ljust(self, max_display_len: int) -> int:
        term_cap = max(self.min_ljust, self._terminal_width() // 2)
        base = min(max(self.min_ljust, max_display_len + 3), term_cap)
        default_idx = self._get_template_token_index("default_padded")
        if default_idx is not None:
            return max(base, default_idx + 1)

        prefix_len = self._get_template_token_index("description")
        if prefix_len is not None:
            return max(base, prefix_len + 1)

        return super().get_commands_ljust(max_display_len)

    def keep_help_default_slot_for_arguments(self, arguments: list["Argument"]) -> bool:
        non_help_args = [arg for arg in arguments if arg.name != "help"]
        if not non_help_args:
            return False

        described = sum(1 for arg in non_help_args if self._has_user_facing_help(arg.help))
        metadata_only = len(non_help_args) - described
        return described >= metadata_only

    @staticmethod
    def _has_user_facing_help(text: str | None) -> bool:
        if text is None:
            return False

        normalized = text.strip()
        if not normalized:
            return False

        return normalized.lower() != "none"

    def _ensure_default_slot_separator_for_overflow(self, values: dict[str, str]) -> dict[str, str]:
        flag_long = values.get("flag_long", "")
        if not flag_long:
            return values

        if ansi_len(strip_ansi(flag_long)) > self.long_flag_width:
            values["flag_long_col"] = values.get("flag_long_col", "") + " "

        return values

    def _build_values_from_argument(self, arg: "Argument") -> dict[str, str]:
        values = super()._build_values_from_argument(arg)
        return self._ensure_default_slot_separator_for_overflow(values)


@dataclass(kw_only=True)
class Aligned(AlignedLayoutBase):
    """Layout with aligned default column and compact flag spacing."""

    format_option: str | None = (
        "{flag_short_col}{flag_long_col}[{default_padded}] {description}{choices_block}"
    )
    format_positional: str | None = "{flag_col}{description}{choices_block}"


@dataclass(kw_only=True)
class AlignedTyped(AlignedLayoutBase):
    """Aligned layout that includes explicit type display."""

    format_option: str | None = (
        "{flag_short_col}{flag_long_col}[{default_padded}] {description} [type: {type}]"
        "{choices_block}"
    )
    format_positional: str | None = "{flag_col}{description} [type: {type}]{choices_block}"


__all__ = [
    "Aligned",
    "AlignedTyped",
]

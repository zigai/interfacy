import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from objinspect import Parameter
from stdl.st import TextStyle, ansi_len, colored, with_style

from interfacy.help.colors import ClapColors, NoColor
from interfacy.help.formatting import format_default_for_help, format_type_for_help
from interfacy.help.layout import HelpLayout
from interfacy.help.style import HelpStyle
from interfacy.help.terminal import strip_ansi
from interfacy.schema.typing import get_param_choices

if TYPE_CHECKING:
    from interfacy.schema.schema import Argument


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


@dataclass(kw_only=True)
class Modern(InterfacyLayout):
    """Modern layout with inline detail rows for defaults and types."""

    include_metavar_in_flag_display: bool = False
    default_field_width: int = 8
    default_label_for_help: str = "default"

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
    use_action_extra: bool = True
    choices_label_text: str = "possible values:"
    default_label_text: str = "default:"
    dashify_metavar: bool = True

    commands_title: str = "Commands:"
    required_indicator: str = ""
    enable_required_indicator: bool = False
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
        return with_style(command_name, self.style.flag_long)


@dataclass(kw_only=True)
class StandardLayout(HelpLayout):
    """Default layout that follows the standard ``argparse`` help output."""

    style: HelpStyle = field(default_factory=NoColor)

    include_metavar_in_flag_display: bool = False
    required_indicator: str = ""
    enable_required_indicator: bool = False
    default_label_for_help: str = ""
    clear_metavar: bool = True

    help_position: int | None = 24
    layout_mode: Literal["auto", "adaptive", "template"] = "adaptive"

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        return " ".join(text.split())

    @classmethod
    def _description_mentions_same_default(cls, description: str, default_text: str) -> bool:
        if not description or not default_text:
            return False

        normalized_description = cls._normalize_whitespace(description).lower()
        normalized_default = cls._normalize_whitespace(default_text).lower()
        if not normalized_default:
            return False

        return f"[default: {normalized_default}]" in normalized_description

    @classmethod
    def _description_mentions_same_choices(
        cls,
        description: str,
        choices_text: str,
    ) -> bool:
        if not description or not choices_text:
            return False

        normalized_description = cls._normalize_whitespace(description).lower()
        normalized_choices = cls._normalize_whitespace(choices_text).lower()
        return f"[choices: {normalized_choices}]" in normalized_description

    @classmethod
    def _with_default_sentence(cls, description: str, has_default: bool, default: Any) -> str:
        if not has_default:
            return description

        default_text = format_default_for_help(default)
        if default_text in {"", '""'}:
            default_text = "''"

        if cls._description_mentions_same_default(description, default_text):
            return description

        default_block = f"[default: {default_text}]"
        if not description:
            return default_block

        return f"{description.rstrip()} {default_block}"

    @classmethod
    def _with_choices_block(
        cls,
        description: str,
        choices: Sequence[Any] | None,
    ) -> str:
        if not choices:
            return description

        choices_text = ", ".join(str(choice) for choice in choices)
        if cls._description_mentions_same_choices(description, choices_text):
            return description

        choices_block = f"[choices: {choices_text}]"
        if not description:
            return choices_block

        return f"{description.rstrip()} {choices_block}"

    def get_help_for_parameter(
        self,
        param: Parameter,
        flags: tuple[str, ...] | None = None,
    ) -> str:
        """
        Return help text following argparse's default style.

        Args:
            param (Parameter): Parameter metadata.
            flags (tuple[str, ...] | None): CLI flags for display.
        """
        description = self.format_description(param.description or "")
        has_default = param.has_default and param.default is not None and not param.is_required
        default_value = param.default
        if has_default and self._param_is_bool(param):
            primary_flag = self._get_primary_boolean_flag(param, flags or ())
            if not primary_flag:
                primary_flag = f"--{(param.name or 'value').replace('_', '-')}"
            rendered_default = self._format_bool_default_for_help(default_value)
            has_default = bool(
                self._suppress_false_default_for_positive_boolean_flag(
                    rendered_default,
                    long_flag=primary_flag,
                )
            )
        description = self._with_default_sentence(description, has_default, default_value)
        choices = get_param_choices(param, for_display=True) if param.is_typed else None

        return self._with_choices_block(description, choices)

    def format_argument(
        self,
        arg: "Argument",
        indent: int = 2,  # noqa: ARG002 - API compatibility
    ) -> str:
        description = self.format_description(arg.help or "")
        has_default = (
            not arg.required
            and arg.argument_default.appears_in_help
            and arg.argument_default.value is not None
        )
        default_value = arg.argument_default.value
        if has_default and self._arg_is_bool(arg):
            if arg.boolean_behavior is not None:
                default_value = arg.boolean_behavior.default
            rendered_default = self._format_bool_default_for_help(default_value)
            has_default = bool(
                self._suppress_false_default_for_positive_boolean_flag(
                    rendered_default,
                    long_flag=self._get_primary_boolean_flag_from_argument(arg),
                )
            )
        description = self._with_default_sentence(description, has_default, default_value)
        choices = (
            [self._format_argument_choice_for_help(arg, choice) for choice in arg.choices]
            if arg.choices
            else None
        )

        return self._with_choices_block(description, choices)


@dataclass(kw_only=True)
class ArgparseLayout(HelpLayout):
    """Layout that follows the default ``argparse`` help output."""

    style: HelpStyle = field(default_factory=NoColor)

    include_metavar_in_flag_display: bool = True
    required_indicator: str = ""
    enable_required_indicator: bool = False
    default_label_for_help: str = ""
    clear_metavar: bool = False

    help_position: int | None = 24
    layout_mode: Literal["auto", "adaptive", "template"] = "adaptive"
    parser_command_usage_suffix: str = "{command}"

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _collapse_duplicate_terminal_period(text: str) -> str:
        if not text:
            return text

        stripped = text.rstrip()
        trailing_ws = text[len(stripped) :]

        if stripped.endswith("..") and not stripped.endswith("..."):
            stripped = stripped[:-1]

        return stripped + trailing_ws

    @classmethod
    def _description_mentions_same_default(cls, description: str, default_text: str) -> bool:
        if not description or not default_text:
            return False

        normalized_description = cls._normalize_whitespace(description).lower()
        normalized_default = cls._normalize_whitespace(default_text).lower()
        if not normalized_default:
            return False

        return (
            f"defaults to {normalized_default}" in normalized_description
            or f"default: {normalized_default}" in normalized_description
        )

    @classmethod
    def _description_mentions_same_choices(
        cls,
        description: str,
        choices_text: str,
    ) -> bool:
        if not description or not choices_text:
            return False

        normalized_description = cls._normalize_whitespace(description).lower()
        normalized_choices = cls._normalize_whitespace(choices_text).lower()
        return (
            f"choices: {normalized_choices}" in normalized_description
            or f"possible values: {normalized_choices}" in normalized_description
        )

    @classmethod
    def _append_sentence(cls, description: str, sentence: str) -> str:
        if not sentence:
            return description

        description = cls._collapse_duplicate_terminal_period(description)

        separator = ""
        if description:
            separator = " " if description.rstrip().endswith((".", "?", "!", ":", ";")) else ". "

        terminal = "" if sentence.endswith((".", "?", "!", ":", ";")) else "."

        return f"{description}{separator}{sentence}{terminal}"

    @classmethod
    def _with_default_sentence(cls, description: str, has_default: bool, default: Any) -> str:
        if not has_default:
            return description

        default_text = format_default_for_help(default)
        if default_text in {"", '""'}:
            default_text = "''"

        if cls._description_mentions_same_default(description, default_text):
            return description

        return cls._append_sentence(description, f"Defaults to {default_text}")

    @classmethod
    def _with_choices_sentence(
        cls,
        description: str,
        choices: Sequence[Any] | None,
    ) -> str:
        if not choices:
            return description

        choices_text = ", ".join(str(choice) for choice in choices)
        if cls._description_mentions_same_choices(description, choices_text):
            return description

        return cls._append_sentence(description, f"Choices: {choices_text}")

    def get_help_for_parameter(
        self,
        param: Parameter,
        flags: tuple[str, ...] | None = None,
    ) -> str:
        """
        Return help text following argparse's default style.

        Args:
            param (Parameter): Parameter metadata.
            flags (tuple[str, ...] | None): CLI flags for display.
        """
        description = self.format_description(param.description or "")
        has_default = param.has_default and param.default is not None and not param.is_required
        default_value = param.default
        if has_default and self._param_is_bool(param):
            primary_flag = self._get_primary_boolean_flag(param, flags or ())
            if not primary_flag:
                primary_flag = f"--{(param.name or 'value').replace('_', '-')}"
            rendered_default = self._format_bool_default_for_help(default_value)
            has_default = bool(
                self._suppress_false_default_for_positive_boolean_flag(
                    rendered_default,
                    long_flag=primary_flag,
                )
            )
        description = self._with_default_sentence(description, has_default, default_value)
        choices = get_param_choices(param, for_display=True) if param.is_typed else None

        return self._with_choices_sentence(description, choices)

    def format_argument(
        self,
        arg: "Argument",
        indent: int = 2,  # noqa: ARG002 - API compatibility
    ) -> str:
        description = self.format_description(arg.help or "")
        has_default = (
            not arg.required
            and arg.argument_default.appears_in_help
            and arg.argument_default.value is not None
        )
        default_value = arg.argument_default.value
        if has_default and self._arg_is_bool(arg):
            if arg.boolean_behavior is not None:
                default_value = arg.boolean_behavior.default
            rendered_default = self._format_bool_default_for_help(default_value)
            has_default = bool(
                self._suppress_false_default_for_positive_boolean_flag(
                    rendered_default,
                    long_flag=self._get_primary_boolean_flag_from_argument(arg),
                )
            )
        description = self._with_default_sentence(description, has_default, default_value)
        choices = (
            [self._format_argument_choice_for_help(arg, choice) for choice in arg.choices]
            if arg.choices
            else None
        )

        return self._with_choices_sentence(description, choices)


__all__ = [
    "Aligned",
    "AlignedTyped",
    "ArgparseLayout",
    "ClapLayout",
    "InterfacyLayout",
    "Modern",
    "StandardLayout",
]

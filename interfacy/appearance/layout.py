import argparse
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from inspect import Parameter as StdParameter
from re import Match
from typing import TYPE_CHECKING, Literal

from objinspect import Class, Function, Method, Parameter
from stdl.st import (
    TextStyle,
    ansi_len,
    colored,
    with_style,
)

from interfacy.naming import CommandNameRegistry, FlagStrategy
from interfacy.util import (
    format_default_for_help,
    format_type_for_help,
    get_param_choices,
    simplified_type_name,
)

if TYPE_CHECKING:  # pragma: no cover
    from interfacy.schema.schema import Argument, Command


@dataclass(kw_only=True)
class InterfacyColors:
    """Base color theme for interfacy."""

    type: TextStyle = TextStyle(color="green")
    type_keyword: TextStyle = TextStyle(color="light_blue")
    type_bracket: TextStyle = TextStyle(color="white")
    type_punctuation: TextStyle = TextStyle(color="white")
    type_operator: TextStyle = TextStyle(color="white")
    type_literal: TextStyle = TextStyle(color="yellow")
    default: TextStyle = TextStyle(color="light_blue")
    description: TextStyle = TextStyle(color="white")
    string: TextStyle = TextStyle(color="yellow")
    extra_data: TextStyle = TextStyle(color="gray")
    flag_short: TextStyle = TextStyle(color="white")
    flag_long: TextStyle = TextStyle(color="white")
    flag_positional: TextStyle = TextStyle(color="white")


@dataclass(kw_only=True)
class HelpLayout:
    """
    Base class for formatting CLI help output.

    Attributes:
        style (InterfacyColors): Color theme for styled output.
        commands_title (str): Heading for command listings.
        prefix_choices (str): Prefix label for choice lists.
        prefix_default (str): Prefix label for default values.
        prefix_type (str): Prefix label for type display.
        required_indicator (str): Marker for required parameters.
        clear_metavar (bool): Hide metavar for optional args when possible.
        simplify_types (bool): Simplify rendered type names.
        enable_required_indicator (bool): Toggle required indicator display.
        required_indicator_pos (Literal["left", "right"]): Required indicator placement.
        min_ljust (int): Minimum left-justify width for command listings.
        command_skips (list[str]): Method names to skip in listings.
        flag_generator (FlagStrategy): Flag strategy used for display.
        name_registry (CommandNameRegistry | None): Registry for canonical names.
        format_option (str | None): Template for option help lines.
        format_positional (str | None): Template for positional help lines.
        help_position (int | None): Column where help text starts.
        default_field_width (int): Width for default value column.
        default_field_width_max (int | None): Max width for default column.
        default_field_width_term_ratio (int): Terminal width ratio for defaults.
        default_field_width_soft_ratio (int): Soft ratio for defaults.
        default_field_width_percentile (float): Percentile used for width sampling.
        default_field_width_small_sample_size (int): Small sample size threshold.
        default_overflow_mode (Literal["inline", "newline"]): Default overflow behavior.
        default_label_for_help (str): Label used for defaults in help.
        include_metavar_in_flag_display (bool): Include metavar in flag display.
        short_flag_width (int): Width for short flag column.
        long_flag_width (int): Width for long flag column.
        pos_flag_width (int): Width for positional column.
        min_total_flag_width (int): Minimum total width for flags.
        usage_prefix (str | None): Optional usage label override.
        usage_style (TextStyle | None): Optional style for usage label.
        usage_text_style (TextStyle | None): Optional style for usage text.
        section_title_map (dict[str, str] | None): Optional section title mapping.
        section_heading_style (TextStyle | None): Optional section title style.
        layout_mode (Literal["auto", "adaptive", "template"]): Layout selection mode.
        doc_inline_code_mode (Literal["bold", "strip"]): Inline code rendering mode.
    """

    style: InterfacyColors = field(default_factory=InterfacyColors)

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
    command_skips: list[str] = field(default_factory=lambda: ["__init__"])
    flag_generator: FlagStrategy | None = None
    name_registry: CommandNameRegistry | None = None

    format_option: str | None = None
    format_positional: str | None = None
    help_position: int | None = None
    default_field_width: int = 7
    default_field_width_max: int | None = None
    default_field_width_term_ratio: int = 5
    default_field_width_soft_ratio: int = 8
    default_field_width_percentile: float = 0.75
    default_field_width_small_sample_size: int = 6
    default_overflow_mode: Literal["inline", "newline"] = "newline"
    default_label_for_help: str = "default"
    suppress_empty_default_brackets_for_help: bool = False
    keep_empty_default_slot_for_help: bool = False
    include_metavar_in_flag_display: bool = True
    short_flag_width: int = 6
    long_flag_width: int = 18
    pos_flag_width: int = 24
    min_total_flag_width: int = 24
    usage_prefix: str | None = None
    usage_style: TextStyle | None = None
    usage_text_style: TextStyle | None = None
    section_title_map: dict[str, str] | None = None
    section_heading_style: TextStyle | None = None
    help_option_description: str = "Show this help message and exit"
    compact_options_usage: bool = False
    parser_command_usage_suffix: str = "[OPTIONS] command [ARGS]"
    subcommand_usage_placeholder: str = "{command}"
    description_before_usage: bool = False

    layout_mode: Literal["auto", "adaptive", "template"] = "auto"

    # "bold":  remove backticks in docstring and make text bold
    # "strip": remove backticks in docstring and leave plain text
    doc_inline_code_mode: Literal["bold", "strip"] = "bold"

    def _get_default_field_width_base(self) -> int:
        base = getattr(self, "_default_field_width_base", None)
        if base is None:
            base = self.default_field_width
            self._default_field_width_base = base
        return base

    def _get_pos_flag_width_base(self) -> int:
        base = getattr(self, "_pos_flag_width_base", None)
        if base is None:
            base = self.pos_flag_width
            self._pos_flag_width_base = base
        return base

    def _compute_default_field_width_for_len(self, max_len: int) -> int:
        base_width = self._get_default_field_width_base()
        if max_len <= 0:
            return base_width

        try:
            term_width = os.get_terminal_size().columns
        except (OSError, AttributeError):
            term_width = 80

        ratio = max(1, getattr(self, "default_field_width_term_ratio", 5))
        term_cap = max(base_width, term_width // ratio)
        if self.default_field_width_max is not None:
            term_cap = min(term_cap, self.default_field_width_max)

        width = min(max_len, term_cap)
        return max(base_width, width)

    def _compute_default_field_width_from_lengths(self, lengths: list[int]) -> int:
        base_width = self._get_default_field_width_base()
        if not lengths:
            return base_width

        try:
            term_width = os.get_terminal_size().columns
        except (OSError, AttributeError):
            term_width = 80

        ratio = max(1, getattr(self, "default_field_width_term_ratio", 5))
        term_cap = max(base_width, term_width // ratio)
        soft_ratio = max(1, getattr(self, "default_field_width_soft_ratio", 8))
        soft_cap = max(base_width, term_width // soft_ratio)
        effective_cap = min(term_cap, soft_cap)
        if self.default_field_width_max is not None:
            effective_cap = min(effective_cap, self.default_field_width_max)

        candidates = [length for length in lengths if length <= effective_cap]
        if not candidates:
            return base_width

        candidates.sort()
        count = len(candidates)
        if count <= self.default_field_width_small_sample_size:
            width = max(candidates)
        else:
            percentile = min(max(self.default_field_width_percentile, 0.0), 1.0)
            idx = max(0, min(count - 1, int((percentile * count + 0.999999) - 1)))
            width = candidates[idx]
        return max(base_width, width)

    def prepare_default_field_width_for_params(self, params: list[Parameter]) -> None:
        """
        Compute default column width from parameter defaults.

        Args:
            params (list[Parameter]): Parameters to inspect.
        """
        if not self._use_template_layout():
            return

        template = self.format_option or self.format_positional or ""
        if "{default_padded}" not in template:
            return

        defaults: list[str] = []
        for param in params:
            if self._param_is_bool(param):
                val = param.default if param.has_default else False
                defaults.append(self._format_bool_default_for_help(val))
            elif not param.is_required and param.default is not None:
                defaults.append(format_default_for_help(param.default))

        lengths = [len(d) for d in defaults if d]
        self.default_field_width = self._compute_default_field_width_from_lengths(lengths)

    def _param_is_bool(self, param: Parameter) -> bool:
        if param.type is bool:
            return True
        if isinstance(param.type, str):
            name = simplified_type_name(param.type)
            base = name.removesuffix("?")
            return base == "bool"
        return False

    def _format_bool_default_for_help(self, value: object) -> str:
        """Render boolean defaults, treating argparse.SUPPRESS as missing."""
        if value is argparse.SUPPRESS:
            return ""
        return "true" if bool(value) else "false"

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
        """
        Format a description string for help output.

        Args:
            description (str): Raw description text.
        """
        return self._format_doc_text(description)

    def get_parser_command_usage_suffix(self) -> str:
        return self.parser_command_usage_suffix

    def get_subcommand_usage_token(self) -> str:
        legacy_placeholder = getattr(self, "subcommand_usage_token", None)
        if isinstance(legacy_placeholder, str):
            return legacy_placeholder
        return self.subcommand_usage_placeholder

    def should_render_description_before_usage(self) -> bool:
        return self.description_before_usage

    def format_usage_metavar(self, name: str, *, is_varargs: bool = False) -> str:
        return f"{name} ..." if is_varargs else name

    def keep_help_default_slot_for_arguments(self, _arguments: list["Argument"]) -> bool:
        return self.keep_empty_default_slot_for_help

    def _collapse_empty_default_slot(
        self,
        rendered: str,
        template: str,
        default_value: str,
        *,
        is_help_option: bool = False,
    ) -> str:
        if not self.suppress_empty_default_brackets_for_help:
            return rendered
        if "{default_padded}" not in template or default_value:
            return rendered

        match = re.search(r"\[\s*\]\s*", rendered)
        if match is None:
            return rendered

        prefix = rendered[: match.start()]
        suffix = rendered[match.end() :]
        if is_help_option and self.keep_empty_default_slot_for_help:
            slot_width = match.end() - match.start()
            return f"{prefix}{' ' * slot_width}{suffix}"

        needs_separator = (
            bool(prefix) and bool(suffix) and not prefix[-1].isspace() and not suffix[0].isspace()
        )
        separator = " " if needs_separator else ""
        return f"{prefix}{separator}{suffix}"

    def get_help_for_parameter(
        self,
        param: Parameter,
        flags: tuple[str, ...] | None = None,
    ) -> str:
        """
        Return help text for a parameter.

        Args:
            param (Parameter): Parameter metadata.
            flags (tuple[str, ...] | None): CLI flags for display, if any.
        """
        if flags is not None and self._use_template_layout():
            return self.format_parameter(param, flags)

        # legacy behavior
        is_varargs = param.kind == StdParameter.VAR_POSITIONAL
        is_required = param.is_required and not is_varargs
        if is_required and not param.is_typed:
            return ""
        parts: list[str] = []

        if self._param_is_bool(param):
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
        if is_required:
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
        """
        Format a command description line for listings.

        Args:
            command (Class | Function | Method): Command to describe.
            ljust (int): Column width for the name.
            name (str | None): Override display name.
            aliases (tuple[str, ...]): Alternate CLI names.
        """
        name = name or command.name
        command_name = self._format_command_display_name(name, aliases)
        name_column = f"   {command_name}".ljust(ljust)
        description = command.description or ""
        return f"{name_column} {with_style(description, self.style.description)}"

    def get_help_for_class(self, command: Class) -> str:
        """
        Build help text for class subcommands.

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
        lines = [self.commands_title]
        for method in command.methods:
            if method.name in self.command_skips:
                continue
            method_name = self.flag_generator.command_translator.translate(method.name)
            lines.append(self.get_command_description(method, ljust, method_name))
        return "\n".join(lines)

    @staticmethod
    def _safe_template_format(template: str, values: dict[str, str]) -> str | None:
        try:
            return template.format(**values)
        except (KeyError, IndexError, TypeError, ValueError):
            return None

    @staticmethod
    def _terminal_width(default: int = 80) -> int:
        try:
            return os.get_terminal_size().columns
        except (OSError, AttributeError):
            return default

    @staticmethod
    def _wrap_plain_words(text: str, wrap_width: int) -> list[str]:
        wrapped: list[str] = []
        for word in text.split():
            if not wrapped:
                wrapped.append(word)
            elif len(wrapped[-1]) + 1 + len(word) <= wrap_width:
                wrapped[-1] = f"{wrapped[-1]} {word}"
            else:
                wrapped.append(word)
        return wrapped

    def _probe_template_field_index(
        self,
        *,
        template: str,
        values: dict[str, str],
        field_name: str,
        marker: str,
    ) -> tuple[str, int]:
        probe_values = dict(values)
        probe_values[field_name] = marker
        probe_render = self._safe_template_format(template, probe_values)
        if probe_render is None:
            return "", -1
        return probe_render, probe_render.find(marker)

    def _prepare_template_default_overflow(
        self,
        *,
        template: str,
        values: dict[str, str],
    ) -> tuple[str, bool]:
        default_overflow = ""
        skip_wrap = False
        if "{default_padded}" in template:
            styled_default = values.get("default", "")
            if styled_default and ansi_len(styled_default) > self.default_field_width:
                overflow_mode = getattr(self, "default_overflow_mode", "newline")
                if overflow_mode == "inline":
                    values["default"] = styled_default
                    values["default_padded"] = styled_default
                    skip_wrap = True
                else:
                    default_overflow = styled_default
                    values["default"] = ""
                    values["default_padded"] = " " * self.default_field_width
        return default_overflow, skip_wrap

    def _apply_template_description_wrapping(
        self,
        *,
        template: str,
        values: dict[str, str],
        raw_description: str,
        indent: int,
        skip_wrap: bool,
        default_overflow: str,
    ) -> None:
        desc_marker = "<<__DESC__>>"
        probe_render, marker_idx = self._probe_template_field_index(
            template=template,
            values=values,
            field_name="description",
            marker=desc_marker,
        )
        if marker_idx == -1:
            return

        prefix_width = ansi_len(probe_render[:marker_idx])
        cont_indent = " " * prefix_width
        wrap_width = max(10, self._terminal_width() - indent - prefix_width)
        wrapped = self._wrap_plain_words(raw_description, wrap_width)

        if wrapped and not skip_wrap:
            styled_lines = [with_style(wrapped[0], self.style.description)]
            if len(wrapped) > 1:
                styled_lines.extend(
                    [cont_indent + with_style(line, self.style.description) for line in wrapped[1:]]
                )
            values["description"] = "\n".join(styled_lines)

        if default_overflow:
            arrow = with_style("→", self.style.extra_data)
            label = with_style("default:", self.style.extra_data)
            overflow_line = f"{arrow} {label} {default_overflow}"
            if values["description"]:
                values["description"] = f"{values['description']}\n{cont_indent}{overflow_line}"
            else:
                values["description"] = f"\n{cont_indent}{overflow_line}"

    @staticmethod
    def _template_fallback_line(values: dict[str, str]) -> str:
        return f"{values['flag']:<40} {values['description']} {values.get('extra', '')}"

    def _finalize_templated_line(
        self,
        *,
        rendered: str,
        template: str,
        values: dict[str, str],
        is_required: bool,
    ) -> str:
        if is_required and values.get("required") and values["required"] not in rendered:
            rendered = f"{rendered} {values['required']}"

        if "[type:" in rendered and "type" in values and not values["type"]:
            rendered = re.sub(r"\s*\[type:\s*\]", "", rendered)

        rendered = self._collapse_empty_default_slot(
            rendered,
            template,
            values.get("default", ""),
            is_help_option=values.get("flag_long", "") == "--help",
        )
        return rendered.rstrip()

    def _format_templated_help_line(
        self,
        *,
        template: str,
        values: dict[str, str],
        raw_description: str,
        indent: int,
        is_required: bool,
    ) -> str:
        default_overflow, skip_wrap = self._prepare_template_default_overflow(
            template=template,
            values=values,
        )
        self._apply_template_description_wrapping(
            template=template,
            values=values,
            raw_description=raw_description,
            indent=indent,
            skip_wrap=skip_wrap,
            default_overflow=default_overflow,
        )

        if not raw_description.strip():
            wrapped_extra = self._wrap_template_field_value(
                template=template,
                values=values,
                field_name="extra",
                indent=indent,
            )
            if wrapped_extra is not None:
                values["extra"] = wrapped_extra

        rendered = self._safe_template_format(template, values)
        if rendered is None:
            rendered = self._template_fallback_line(values)

        return self._finalize_templated_line(
            rendered=rendered,
            template=template,
            values=values,
            is_required=is_required,
        )

    def format_parameter(self, param: Parameter, flags: tuple[str, ...]) -> str:
        """
        Format a parameter using the active layout template.

        Args:
            param (Parameter): Parameter metadata.
            flags (tuple[str, ...]): CLI flags for the parameter.
        """
        _, _, _, is_option = self._build_flag_parts(param, flags)
        template = self.format_option if is_option else self.format_positional
        if not template:
            return HelpLayout.get_help_for_parameter(self, param, None)

        values = self._build_values(param, flags)
        raw_description = self._format_doc_text(param.description or "")
        is_varargs = param.kind == StdParameter.VAR_POSITIONAL
        is_required = param.is_required and not is_varargs
        return self._format_templated_help_line(
            template=template,
            values=values,
            raw_description=raw_description,
            indent=2,  # argparse adds a fixed two-space indent for each help line
            is_required=is_required,
        )

    def get_help_for_multiple_commands(self, commands: dict[str, "Command"]) -> str:
        """
        Build a command listing for multiple top-level commands.

        Args:
            commands (dict[str, Command]): Command map keyed by name.
        """
        display_names = [
            self._format_command_display_name(cmd.cli_name, cmd.aliases)
            for cmd in commands.values()
        ]
        max_display = max([len(name) for name in display_names], default=0)
        ljust = self.get_commands_ljust(max_display)
        lines = [self.commands_title]
        for command in commands.values():
            cli_name = command.cli_name
            if command.obj is None:
                command_name = self._format_command_display_name(cli_name, command.aliases)
                name_column = f"   {command_name}".ljust(ljust)
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

    def _use_template_layout(self) -> bool:
        match self.layout_mode:
            case "template":
                return True
            case "adaptive":
                return False
        has_templates = bool(self.format_option or self.format_positional)
        return has_templates

    def _command_layout_probe_values(self) -> dict[str, str]:
        values = {
            "flag": "",
            "flag_short": "",
            "flag_long": "",
            "flag_short_col": " " * self.short_flag_width,
            "flag_long_col": " " * self.long_flag_width,
            "flag_col": " " * self.pos_flag_width,
            "description": "",
            "type": "",
            "default": "",
            "default_padded": " " * self.default_field_width,
            "choices": "",
            "choices_label": "",
            "choices_block": "",
            "extra": "",
            "details": "",
            "required": "",
            "metavar": "",
        }
        if hasattr(self, "column_gap"):
            values["column_gap"] = self.column_gap
        return values

    def _get_template_token_index(self, field_name: str) -> int | None:
        if not self._use_template_layout():
            return None

        template = self.format_option or self.format_positional
        if not template:
            return None

        marker = f"<<__{field_name}__>>"
        values = self._command_layout_probe_values()
        values[field_name] = marker
        probe_render = self._safe_template_format(template, values)
        marker_idx = probe_render.find(marker) if probe_render is not None else -1

        if marker_idx == -1:
            return None

        if (
            field_name == "default_padded"
            and marker_idx > 0
            and probe_render[marker_idx - 1] == "["
        ):
            return marker_idx - 1

        return marker_idx

    def _get_commands_prefix_len(self) -> int | None:
        if not self._use_template_layout():
            return None

        template = self.format_option or self.format_positional
        if not template:
            return None

        return self._get_template_token_index("description")

    def _wrap_template_field_value(
        self,
        *,
        template: str,
        values: dict[str, str],
        field_name: str,
        indent: int,
    ) -> str | None:
        raw_value = values.get(field_name, "")
        if not raw_value or "\n" in raw_value:
            return None

        marker = f"<<__{field_name.upper()}__>>"
        probe_render, marker_idx = self._probe_template_field_index(
            template=template,
            values=values,
            field_name=field_name,
            marker=marker,
        )

        if marker_idx == -1:
            return None

        prefix_str = probe_render[:marker_idx]
        prefix_width = ansi_len(prefix_str)
        term_width = self._terminal_width()

        wrap_width = max(10, term_width - indent - prefix_width)
        normalized = " ".join(raw_value.split())
        if ansi_len(normalized) <= wrap_width:
            return None

        wrapped: list[str] = []
        for word in normalized.split():
            if not wrapped:
                wrapped.append(word)
            elif ansi_len(wrapped[-1]) + 1 + ansi_len(word) <= wrap_width:
                wrapped[-1] = f"{wrapped[-1]} {word}"
            else:
                wrapped.append(word)

        if len(wrapped) <= 1:
            return None

        cont_indent = " " * (prefix_width + indent)
        return wrapped[0] + "".join(f"\n{cont_indent}{line}" for line in wrapped[1:])

    def get_commands_ljust(self, max_display_len: int) -> int:
        """
        Compute the left-justify width for command listings.

        Args:
            max_display_len (int): Maximum display name length.
        """
        base = max(self.min_ljust, max_display_len + 3)
        default_idx = self._get_template_token_index("default_padded")
        prefix_len = self._get_commands_prefix_len()
        align_idx = default_idx if default_idx is not None else prefix_len

        if align_idx is None:
            if isinstance(self.help_position, int):
                desired = self.help_position - 1
                return max(base, desired)
            return base
        desired = align_idx + 1  # align to target column (indent=2)
        return max(base, desired)

    def _get_param_extra_help(self, param: Parameter) -> str:
        parts: list[str] = []
        default_added = False
        if param.is_typed and not self._param_is_bool(param):
            if choices := get_param_choices(param, for_display=True):
                param_info = self.prefix_choices + ", ".join(
                    [with_style(str(i), self.style.string) for i in choices]
                )
                if not param.is_required:
                    default_text = self.prefix_default + with_style(
                        format_default_for_help(param.default), self.style.default
                    )
                    param_info += ", " + default_text
                    default_added = True
            else:
                type_str = format_type_for_help(param.type, self.style.type, theme=self.style)
                param_info = self.prefix_type + type_str

            parts.append(param_info)

        if (
            param.is_optional
            and param.default is not None
            and not self._param_is_bool(param)
            and not default_added
        ):
            parts.append(", ")
            parts.append(
                self.prefix_default
                + with_style(format_default_for_help(param.default), self.style.default)
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
        needs_value = param.is_typed and not self._param_is_bool(param)
        if is_option:
            if needs_value and self.include_metavar_in_flag_display:
                metavar = (param.name or "value").upper()
        else:  # Always show uppercase name for positional arguments
            metavar = (param.name or "value").upper()

        def with_metavar(flag: str) -> str:
            return f"{flag} {metavar}" if metavar else flag

        is_bool_param = param.is_typed and self._param_is_bool(param)
        if is_bool_param:
            primary_flag = self._get_primary_boolean_flag(param, flags)
            flag_short = shorts[0] if shorts else ""
            flag_long = primary_flag
            joined = f"{flag_short}, {flag_long}" if flag_short else flag_long
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

    def _format_choice_for_help(self, value: object) -> str:
        if isinstance(value, Enum):
            raw = value.value
            if isinstance(raw, str):
                return raw
            return value.name
        return str(value)

    def _format_argument_choice_for_help(self, arg: "Argument", value: object) -> str:
        enum_type = arg.type
        if isinstance(value, str) and isinstance(enum_type, type) and issubclass(enum_type, Enum):
            enum_member = enum_type.__members__.get(value)
            if enum_member is not None:
                return self._format_choice_for_help(enum_member)
        return self._format_choice_for_help(value)

    @staticmethod
    def _enum_matches(value: object, member_name: str) -> bool:
        member = getattr(type(value), member_name, None)
        return value == member

    def _type_for_argument_help(self, arg: "Argument") -> object | None:
        if arg.type is None:
            return None

        if self._enum_matches(arg.value_shape, "LIST"):
            try:
                return list[arg.type]
            except TypeError:
                return arg.type

        if (
            self._enum_matches(arg.value_shape, "TUPLE")
            and isinstance(arg.nargs, int)
            and arg.nargs > 1
        ):
            try:
                return tuple.__class_getitem__(tuple([arg.type] * arg.nargs))
            except TypeError:
                return arg.type

        return arg.type

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

        active_pos_width = max(
            self._get_pos_flag_width_base(),
            getattr(self, "_active_pos_flag_width", self.pos_flag_width),
        )

        if flag:
            fp = styled_values["flag_styled"]
            pad = max(0, active_pos_width - ansi_len(fp))
            styled_values["flag_col"] = f"{fp}{' ' * pad}"
        else:
            styled_values["flag_col"] = " " * active_pos_width

        return styled_values

    def _build_values(self, param: Parameter, flags: tuple[str, ...]) -> dict[str, str]:
        flag, flag_short, flag_long, is_option = self._build_flag_parts(param, flags)

        description = self._format_doc_text(param.description or "")
        if description and not description.endswith((".", "?", "!")) and self._param_is_bool(param):
            description += "."
        description = with_style(description, self.style.description)

        default_raw = ""
        if self._param_is_bool(param):
            val = param.default if param.has_default else False
            default_raw = self._format_bool_default_for_help(val)
        elif not param.is_required and param.default is not None:
            default_raw = format_default_for_help(param.default)

        styled_default = with_style(default_raw, self.style.default) if default_raw else ""
        pad = max(0, self.default_field_width - ansi_len(styled_default))
        default_padded = f"{' ' * pad}{styled_default}"
        default = styled_default

        choices = get_param_choices(param, for_display=True) if param.is_typed else None
        choices_str = ""
        if choices:
            choices_str = ", ".join([with_style(str(i), self.style.string) for i in choices])
        choices_label = "choices:" if choices_str else ""
        choices_block = " [" + choices_label + " " + choices_str + "]" if choices_str else ""

        if param.is_typed and not self._param_is_bool(param) and not choices:
            type_str = format_type_for_help(param.type, self.style.type, theme=self.style)
        else:
            type_str = ""

        is_varargs = param.kind == StdParameter.VAR_POSITIONAL
        is_required = param.is_required and not is_varargs

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
            "required": self.required_indicator if is_required else "",
            "metavar": (param.name or "value").upper(),
        }

        values.update(self._build_styled_columns(flag_short, flag_long, flag, is_option))

        return values

    def _arg_is_bool(self, arg: "Argument") -> bool:
        return self._enum_matches(arg.value_shape, "FLAG")

    def is_argument_boolean(self, arg: "Argument") -> bool:
        return self._arg_is_bool(arg)

    def _arg_has_default(self, arg: "Argument") -> bool:
        return arg.default is not None and arg.default is not argparse.SUPPRESS

    def _get_primary_boolean_flag_from_argument(self, arg: "Argument") -> str:
        longs = [f for f in arg.flags if f.startswith("--")]
        if not longs:
            return arg.flags[0] if arg.flags else ""

        base_flag = None
        no_flag = None
        for flag in longs:
            if flag.startswith("--no-"):
                no_flag = flag
            else:
                base_flag = flag

        if base_flag and not no_flag:
            no_flag = f"--no-{base_flag[2:]}"

        if arg.boolean_behavior is not None:
            default_value = arg.boolean_behavior.default
        else:
            default_value = arg.default if self._arg_has_default(arg) else False

        if default_value is True and no_flag:
            return no_flag
        return base_flag or longs[0]

    def get_primary_boolean_flag_for_argument(self, arg: "Argument") -> str:
        return self._get_primary_boolean_flag_from_argument(arg)

    def _build_flag_parts_from_argument(self, arg: "Argument") -> tuple[str, str, str, bool]:
        shorts = [f for f in arg.flags if f.startswith("-") and not f.startswith("--")]
        longs = [f for f in arg.flags if f.startswith("--")]
        is_option = self._enum_matches(arg.kind, "OPTION")

        metavar = ""
        is_bool = self._arg_is_bool(arg)
        needs_value = arg.type is not None and not is_bool
        if is_option:
            if needs_value and self.include_metavar_in_flag_display:
                metavar = (arg.metavar or arg.display_name or arg.name or "value").upper()
        else:
            metavar = (arg.metavar or arg.display_name or arg.name or "value").upper()

        def with_metavar(flag: str) -> str:
            return f"{flag} {metavar}" if metavar else flag

        if is_bool:
            primary_flag = self._get_primary_boolean_flag_from_argument(arg)
            flag_short = shorts[0] if shorts else ""
            flag_long = primary_flag
            joined = f"{flag_short}, {flag_long}" if flag_short else flag_long
            return joined, flag_short, flag_long, is_option

        flag_short = with_metavar(shorts[0]) if shorts else ""
        flag_long = with_metavar(longs[0]) if longs else ""

        if is_option:
            joined = ", ".join([p for p in (flag_short, flag_long) if p])
        else:
            joined = metavar or (arg.name or "")

        return joined, flag_short, flag_long, is_option

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
                        format_default_for_help(arg.default), self.style.default
                    )
                    param_info += ", " + default_text
                    default_added = True
            else:
                type_str = format_type_for_help(
                    self._type_for_argument_help(arg), self.style.type, theme=self.style
                )
                param_info = self.prefix_type + type_str
            parts.append(param_info)

        if not arg.required and self._arg_has_default(arg) and not is_bool and not default_added:
            parts.append(", ")
            parts.append(
                self.prefix_default
                + with_style(format_default_for_help(arg.default), self.style.default)
            )

        if not parts:
            return ""
        return f"[{''.join(parts)}]"

    def _build_values_from_argument(self, arg: "Argument") -> dict[str, str]:
        flag, flag_short, flag_long, is_option = self._build_flag_parts_from_argument(arg)

        is_bool = self._arg_is_bool(arg)
        description = self._format_doc_text(arg.help or "")
        if description and not description.endswith((".", "?", "!")) and is_bool:
            description += "."
        description = with_style(description, self.style.description)

        default_raw = ""
        if is_bool:
            is_synthetic_help = arg.name == "help" and "--help" in arg.flags
            if not is_synthetic_help:
                if arg.boolean_behavior is not None:
                    val = arg.boolean_behavior.default
                elif self._arg_has_default(arg):
                    val = arg.default
                else:
                    val = False
                default_raw = self._format_bool_default_for_help(val)
        elif not arg.required and self._arg_has_default(arg):
            default_raw = format_default_for_help(arg.default)

        styled_default = with_style(default_raw, self.style.default) if default_raw else ""
        pad = max(0, self.default_field_width - ansi_len(styled_default))
        default_padded = f"{' ' * pad}{styled_default}"
        default = styled_default

        choices_str = ""
        if arg.choices:
            choices_str = ", ".join(
                [
                    with_style(self._format_argument_choice_for_help(arg, i), self.style.string)
                    for i in arg.choices
                ]
            )
        choices_label = "choices:" if choices_str else ""
        choices_block = f" [{choices_label} {choices_str}]" if choices_str else ""

        arg_type_for_help = self._type_for_argument_help(arg)
        is_typed = arg_type_for_help is not None
        if is_typed and not is_bool and not arg.choices:
            type_str = format_type_for_help(arg_type_for_help, self.style.type, theme=self.style)
        else:
            type_str = ""

        is_varargs = self._enum_matches(arg.value_shape, "LIST") and not is_option
        is_required = arg.required and not is_varargs

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
            "extra": self._build_extra_from_argument(arg),
            "required": self.required_indicator if is_required else "",
            "metavar": (arg.metavar or arg.display_name or arg.name or "value").upper(),
        }

        values.update(self._build_styled_columns(flag_short, flag_long, flag, is_option))
        return values

    def format_argument(self, arg: "Argument", indent: int = 2) -> str:
        is_option = self._enum_matches(arg.kind, "OPTION")
        template = self.format_option if is_option else self.format_positional
        if not template:
            return self._format_argument_legacy(arg, indent)

        values = self._build_values_from_argument(arg)
        raw_description = self._format_doc_text(arg.help or "")
        is_varargs = self._enum_matches(arg.value_shape, "LIST") and is_option is False
        is_required = arg.required and not is_varargs
        return self._format_templated_help_line(
            template=template,
            values=values,
            raw_description=raw_description,
            indent=indent,
            is_required=is_required,
        )

    def _format_argument_legacy(self, arg: "Argument", _indent: int = 2) -> str:
        is_bool = self._arg_is_bool(arg)
        is_required = arg.required
        is_typed = arg.type is not None

        if is_required and not is_typed:
            return ""

        parts: list[str] = []
        if is_bool:
            if arg.help:
                description = self._format_doc_text(arg.help)
                if not description.endswith((".", "?", "!")):
                    description += "."
                parts.append(with_style(description, self.style.description))
        else:
            if arg.help:
                parts.append(
                    f"{with_style(self._format_doc_text(arg.help), self.style.description)} "
                )
            parts.append(self._build_extra_from_argument(arg))

        text = "".join(parts)
        if is_required:
            if self.required_indicator_pos == "left":
                text = f"{self.required_indicator} {text}"
            else:
                text = f"{text} {self.required_indicator}"
        return text

    def prepare_default_field_width_for_arguments(self, arguments: list["Argument"]) -> None:
        template = self.format_option or self.format_positional or ""
        self._active_pos_flag_width = self._get_pos_flag_width_base()

        if "{flag_col}" in template:
            max_flag_len = 0
            for argument in arguments:
                flag, _, _, _ = self._build_flag_parts_from_argument(argument)
                max_flag_len = max(max_flag_len, ansi_len(flag))
            self._active_pos_flag_width = max(self._active_pos_flag_width, max_flag_len)

        if "{default_padded}" not in template:
            return

        defaults: list[str] = []
        for arg in arguments:
            if self._arg_is_bool(arg):
                if arg.boolean_behavior is not None:
                    val = arg.boolean_behavior.default
                elif self._arg_has_default(arg):
                    val = arg.default
                else:
                    val = False
                defaults.append(self._format_bool_default_for_help(val))
            elif not arg.required and self._arg_has_default(arg):
                defaults.append(format_default_for_help(arg.default))

        lengths = [len(d) for d in defaults if d]
        self.default_field_width = self._compute_default_field_width_from_lengths(lengths)


__all__ = [
    "HelpLayout",
    "InterfacyColors",
]

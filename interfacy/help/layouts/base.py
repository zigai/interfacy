from copy import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from objinspect import Class, Function, Method
from stdl.st import TextStyle, with_style

from interfacy.common.terminal import get_terminal_width
from interfacy.declarations.sorting import (
    DEFAULT_HELP_OPTION_SORT_RULES,
    DEFAULT_HELP_SUBCOMMAND_SORT_RULES,
    HelpOptionSortRule,
    HelpSubcommandSortRule,
)
from interfacy.help.colors import InterfacyColors
from interfacy.help.formatting import format_doc_inline_code
from interfacy.help.layouts.arguments import (
    adaptive_argument_flag,
    build_argument_values,
    build_extra,
    build_flag_parts,
    build_styled_columns,
    default_column_texts,
    enum_matches,
    format_argument_choice,
    format_argument_row,
    format_bool_default,
    format_choice,
    has_help_default,
    is_boolean_argument,
    primary_boolean_flag,
    suppress_false_default_for_positive_boolean_flag,
    type_for_argument_help,
)
from interfacy.help.layouts.columns import (
    compute_default_field_width,
    flag_column_width,
    format_adaptive_row,
    template_token_index,
)
from interfacy.help.layouts.commands import (
    commands_ljust_width,
    format_command_display_name,
    format_command_row,
    render_command_listing,
)
from interfacy.help.ordering import order_command_list, order_option_arguments
from interfacy.help.style import HelpStyle

if TYPE_CHECKING:  # pragma: no cover
    from interfacy.schema import Argument, Command


@dataclass
class LayoutMeasurements:
    terminal_width: int | None = None
    default_field_width_base: int | None = None
    pos_flag_width_base: int | None = None
    active_pos_flag_width: int | None = None


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
        required_indicator_pos (Literal["left", "right"]): Required indicator placement.
        min_ljust (int): Minimum left-justify width for command listings.
        command_indent (int): Leading spaces before command rows.
        command_group_spacing (int): Blank lines between grouped command sections.
        format_option (str | None): Template for option help lines.
        format_positional (str | None): Template for positional help lines.
        help_position (int | None): Column where help text starts.
        default_field_width (int): Width for default value column.
        default_field_width_max (int | None): Max width for default column.
        default_field_width_term_ratio (int): Terminal width ratio for defaults.
        default_overflow_mode (Literal["inline", "newline"]): Default overflow behavior.
        include_metavar_in_flag_display (bool): Include metavar in flag display.
        short_flag_width (int): Width for short flag column.
        long_flag_width (int): Width for long flag column.
        pos_flag_width (int): Width for positional column.
        usage_prefix (str | None): Optional usage label override.
        section_title_map (dict[str, str] | None): Optional section title mapping.
        help_option_sort_default (list[HelpOptionSortRule] | None): Optional layout-level
            default sorting rules.
        help_option_sort_rules (list[HelpOptionSortRule]): Active sorting rules.
        help_subcommand_sort_default (list[HelpSubcommandSortRule] | None): Optional
            layout-level default sorting rules for command/subcommand rows.
        help_subcommand_sort_rules (list[HelpSubcommandSortRule]): Active command/subcommand
            sorting rules.
        layout_mode (Literal["auto", "adaptive", "template"]): Layout selection mode.
        doc_inline_code_mode (Literal["bold", "strip"]): Inline code rendering mode.
    """

    style: HelpStyle = field(default_factory=InterfacyColors)

    commands_title: str = "commands:"
    prefix_choices: str = "choices: "
    prefix_default: str = "default="
    prefix_type: str = "type: "
    required_indicator: str = "(*)"

    clear_metavar: bool = True

    required_indicator_pos: Literal["left", "right"] = "right"
    min_ljust: int = 19
    command_indent: int = 3
    command_group_spacing: int = 1

    format_option: str | None = None
    format_positional: str | None = None
    help_position: int | None = None
    default_field_width: int = 7
    default_field_width_max: int | None = None
    default_field_width_term_ratio: int = 5
    default_overflow_mode: Literal["inline", "newline"] = "newline"
    suppress_empty_default_brackets_for_help: bool = False
    keep_empty_default_slot_for_help: bool = False
    include_metavar_in_flag_display: bool = True
    short_flag_width: int = 6
    long_flag_width: int = 18
    pos_flag_width: int = 24
    usage_prefix: str | None = None
    section_title_map: dict[str, str] | None = None
    help_option_description: str = "Show this help message and exit"
    compact_options_usage: bool = False
    parser_command_usage_suffix: str = "[OPTIONS] command [ARGS]"
    subcommand_usage_placeholder: str = "{command}"
    description_before_usage: bool = False
    help_option_sort_default: list[HelpOptionSortRule] | None = None
    help_option_sort_rules: list[HelpOptionSortRule] = field(
        default_factory=lambda: list(DEFAULT_HELP_OPTION_SORT_RULES)
    )
    help_subcommand_sort_default: list[HelpSubcommandSortRule] | None = None
    help_subcommand_sort_rules: list[HelpSubcommandSortRule] = field(
        default_factory=lambda: list(DEFAULT_HELP_SUBCOMMAND_SORT_RULES)
    )

    layout_mode: Literal["auto", "adaptive", "template"] = "auto"

    # "bold":  remove backticks in docstring and make text bold
    # "strip": remove backticks in docstring and leave plain text
    doc_inline_code_mode: Literal["bold", "strip"] = "bold"
    _measurements: LayoutMeasurements = field(
        default_factory=LayoutMeasurements, init=False, repr=False, compare=False
    )

    def _for_render(self, terminal_width: int) -> "HelpLayout":
        layout = copy(self)
        layout._measurements = LayoutMeasurements(terminal_width=terminal_width)
        return layout

    def _terminal_width(self, default: int = 80) -> int:
        width = self._measurements.terminal_width
        return width if width is not None else get_terminal_width(default)

    def _get_default_field_width_base(self) -> int:
        base = self._measurements.default_field_width_base
        if base is None:
            base = self.default_field_width
            self._measurements.default_field_width_base = base

        return base

    def _get_pos_flag_width_base(self) -> int:
        base = self._measurements.pos_flag_width_base
        if base is None:
            base = self.pos_flag_width
            self._measurements.pos_flag_width_base = base

        return base

    def _compute_default_field_width_for_len(self, max_len: int) -> int:
        base_width = self._get_default_field_width_base()
        if max_len <= 0:
            return base_width

        return compute_default_field_width(
            max_len,
            base_width=base_width,
            terminal_width=self._terminal_width(),
            term_ratio=self.default_field_width_term_ratio,
            width_max=self.default_field_width_max,
        )

    def _compute_default_field_width_from_lengths(self, lengths: list[int]) -> int:
        if not lengths:
            return self._get_default_field_width_base()

        return self._compute_default_field_width_for_len(max(lengths))

    def _use_template_layout(self) -> bool:
        match self.layout_mode:
            case "template":
                return True
            case "adaptive":
                return False
            case "auto":
                return bool(self.format_option or self.format_positional)

    def _get_template_token_index(self, field_name: str) -> int | None:
        return template_token_index(self, field_name)

    def _format_doc_text(self, text: str) -> str:
        """Format inline code spans wrapped in backticks in docstrings."""
        return format_doc_inline_code(text, mode=self.doc_inline_code_mode)

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
        """Return the subcommand placeholder token used in usage lines."""
        return self.subcommand_usage_placeholder

    def should_render_description_before_usage(self) -> bool:
        return self.description_before_usage

    def format_usage_metavar(self, name: str, *, is_varargs: bool = False) -> str:
        """
        Format a metavar token for usage output.

        Args:
            name (str): Base metavar text.
            is_varargs (bool): Whether the metavar represents varargs.
        """
        return f"{name} ..." if is_varargs else name

    def keep_help_default_slot_for_arguments(self, arguments: list["Argument"]) -> bool:
        """
        Decide whether to preserve the empty default column for help rows.

        Args:
            arguments (list[Argument]): Argument rows being rendered.
        """
        del arguments

        return self.keep_empty_default_slot_for_help

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
        command_name = self._format_command_display_name(name or command.name, aliases)
        return format_command_row(self, command_name, command.description or "", ljust)

    def _format_commands_title(self) -> str:
        return self.commands_title

    def _format_command_name_for_help(self, command_name: str) -> str:
        return command_name

    def _format_command_display_name(self, name: str, aliases: tuple[str, ...] = ()) -> str:
        return format_command_display_name(name, aliases)

    def get_help_for_multiple_commands(
        self,
        commands: dict[str, "Command"],
        *,
        rules: list[HelpSubcommandSortRule] | None = None,
    ) -> str:
        """
        Build a command listing for multiple top-level commands.

        Args:
            commands (dict[str, Command]): Command map keyed by name.
            rules (list[HelpSubcommandSortRule] | None): Optional explicit ordering rules.
        """
        return render_command_listing(self, commands, rules=rules)

    def order_commands_for_help(
        self,
        commands: dict[str, "Command"],
        *,
        rules: list[HelpSubcommandSortRule] | None = None,
    ) -> list["Command"]:
        """
        Return commands sorted by the active help-subcommand ordering rules.

        Args:
            commands (dict[str, Command]): Command map keyed by canonical name.
            rules (list[HelpSubcommandSortRule] | None): Optional explicit ordering rules.
        """
        return order_command_list(self, list(commands.values()), rules=rules)

    def get_commands_ljust(self, max_display_len: int) -> int:
        """
        Compute the left-justify width for command listings.

        Args:
            max_display_len (int): Maximum display name length.
        """
        return commands_ljust_width(self, max_display_len)

    def _format_choice_for_help(self, value: Any) -> str:
        return format_choice(value)

    def _format_argument_choice_for_help(self, arg: "Argument", value: Any) -> str:
        return format_argument_choice(arg, value)

    @staticmethod
    def _enum_matches(value: Any, member_name: str) -> bool:
        return enum_matches(value, member_name)

    def _type_for_argument_help(self, arg: "Argument") -> Any | None:
        return type_for_argument_help(arg)

    @staticmethod
    def _format_bool_default_for_help(value: Any) -> str:
        return format_bool_default(value)

    def _suppress_false_default_for_positive_boolean_flag(
        self,
        default_text: str,
        *,
        long_flag: str,
    ) -> str:
        return suppress_false_default_for_positive_boolean_flag(
            default_text,
            long_flag=long_flag,
        )

    def _style_flag_token(self, flag: str, style: TextStyle) -> str:
        return with_style(flag, style)

    def _build_styled_columns(
        self, flag_short: str, flag_long: str, flag: str, is_option: bool
    ) -> dict[str, str]:
        """
        Build styled flag strings with proper column padding.
        Accounts for ANSI color codes when calculating padding.
        """
        measured_pos_width = self._measurements.active_pos_flag_width
        pos_width = max(
            self._get_pos_flag_width_base(),
            measured_pos_width if measured_pos_width is not None else self.pos_flag_width,
        )

        return build_styled_columns(
            self,
            flag_short,
            flag_long,
            flag,
            is_option=is_option,
            pos_width=pos_width,
        )

    def _arg_is_bool(self, arg: "Argument") -> bool:
        return is_boolean_argument(arg)

    def is_argument_boolean(self, arg: "Argument") -> bool:
        """
        Return whether an argument schema represents a boolean flag.

        Args:
            arg (Argument): Argument schema to inspect.
        """
        return self._arg_is_bool(arg)

    @staticmethod
    def _arg_has_default(arg: "Argument") -> bool:
        return has_help_default(arg)

    def _get_primary_boolean_flag_from_argument(self, arg: "Argument") -> str:
        return primary_boolean_flag(arg)

    def get_primary_boolean_flag_for_argument(self, arg: "Argument") -> str:
        """
        Return the canonical flag token used to display a boolean option.

        Args:
            arg (Argument): Argument schema describing a boolean flag.
        """
        return self._get_primary_boolean_flag_from_argument(arg)

    def _build_flag_parts_from_argument(self, arg: "Argument") -> tuple[str, str, str, bool]:
        return build_flag_parts(
            arg,
            include_metavar=self.include_metavar_in_flag_display,
        )

    def _build_extra_from_argument(self, arg: "Argument") -> str:
        return build_extra(self, arg)

    def _build_values_from_argument(self, arg: "Argument") -> dict[str, str]:
        return build_argument_values(self, arg)

    def order_option_arguments_for_help(
        self,
        options: list["Argument"],
        *,
        rules: list[HelpOptionSortRule] | None = None,
    ) -> list["Argument"]:
        """
        Return options sorted by the active help-option ordering rules.

        Args:
            options (list[Argument]): Option arguments to sort.
            rules (list[HelpOptionSortRule] | None): Optional explicit ordering rules.
        """
        return order_option_arguments(self, options, rules=rules)

    def format_argument(self, arg: "Argument", indent: int = 2) -> str:
        """
        Format one argument schema as a rendered help line.

        Args:
            arg (Argument): Argument schema to render.
            indent (int): Leading indent width in spaces.
        """
        return format_argument_row(self, arg, indent)

    def _adaptive_argument_flag(self, arg: "Argument") -> str:
        return adaptive_argument_flag(self, arg)

    def format_adaptive_argument_row(self, arg: "Argument") -> str:
        """Format one schema argument with its flag/name column for adaptive layouts."""
        return format_adaptive_row(
            self._adaptive_argument_flag(arg),
            self.format_argument(arg),
            help_position=self.help_position,
            terminal_width=self._terminal_width(),
        )

    def prepare_default_field_width_for_arguments(self, arguments: list["Argument"]) -> None:
        """
        Compute default-column widths for a batch of rendered arguments.

        Args:
            arguments (list[Argument]): Argument schemas rendered in one help section.
        """
        template = self.format_option or self.format_positional or ""
        self._measurements.active_pos_flag_width = flag_column_width(
            self,
            arguments,
            template=template,
            base_width=self._get_pos_flag_width_base(),
        )

        if "{default_padded}" not in template:
            return

        defaults = default_column_texts(arguments)
        lengths = [len(default) for default in defaults if default]
        self.default_field_width = self._compute_default_field_width_from_lengths(lengths)


__all__ = [
    "HelpLayout",
    "LayoutMeasurements",
]

"""Command listing rows and help groups for help layouts."""

from typing import TYPE_CHECKING

from stdl.st import ansi_len, with_style

from interfacy.declarations.sorting import HelpSubcommandSortRule
from interfacy.help.ordering import order_command_list
from interfacy.help.wrapping import wrap_plain_words, wrap_text_preserving_words

if TYPE_CHECKING:  # pragma: no cover
    from interfacy.help.layouts.base import HelpLayout
    from interfacy.help.style import HelpStyle
    from interfacy.schema import Command


def format_command_display_name(name: str, aliases: tuple[str, ...] = ()) -> str:
    """Return a command name followed by its aliases in parentheses."""
    if not aliases:
        return name

    return f"{name} ({', '.join(aliases)})"


def format_command_group_heading(group_title: str, style: "HelpStyle") -> str:
    """Return a help-group heading styled like a section heading."""
    if style.section_heading_style is None:
        return group_title

    return with_style(group_title, style.section_heading_style)


def commands_ljust_width(layout: "HelpLayout", max_display_len: int) -> int:
    """
    Return the name column width for command rows, aligned to the argument help column.

    Args:
        layout (HelpLayout): Layout providing widths and templates.
        max_display_len (int): Widest command display name.
    """
    term_cap = max(layout.min_ljust, layout._terminal_width() // 2)
    base = min(max(layout.min_ljust, max_display_len + 3), term_cap)
    default_idx = layout._get_template_token_index("default_padded")
    prefix_len = layout._get_template_token_index("description")
    align_idx = default_idx if default_idx is not None else prefix_len

    if align_idx is not None:
        return max(base, align_idx + 1)
    if isinstance(layout.help_position, int):
        return max(base, layout.help_position + 1)

    return base


def format_command_row(
    layout: "HelpLayout",
    command_name: str,
    description: str,
    ljust: int,
) -> str:
    """
    Render one command row with its description wrapped to the terminal.

    Args:
        layout (HelpLayout): Layout providing indent, styles, and terminal width.
        command_name (str): Display name of the command.
        description (str): Command description.
        ljust (int): Name column width.
    """
    description_style = layout.style.description
    name_styled = layout._format_command_name_for_help(command_name)
    pad = max(0, ljust - len(command_name) - layout.command_indent)
    name_column = f"{' ' * layout.command_indent}{name_styled}{' ' * pad}"
    prefix = f"{name_column} "
    if not description:
        return prefix.rstrip()

    prefix_width = ansi_len(prefix)
    target_width = max(10, layout._terminal_width() - 2)
    if prefix_width > target_width - 10:
        desc_indent_width = min(max(layout.command_indent + 2, ljust + 1), target_width - 10)
        desc_indent = " " * desc_indent_width
        wrapped = wrap_text_preserving_words(
            description,
            width=target_width,
            initial_indent=desc_indent,
            subsequent_indent=desc_indent,
        )
        if not wrapped:
            return name_column.rstrip()

        lines = [name_column.rstrip()]
        lines.extend(with_style(line, description_style) for line in wrapped)

        return "\n".join(lines)

    wrapped = wrap_plain_words(description, max(10, target_width - prefix_width))
    if not wrapped:
        return prefix.rstrip()

    lines = [f"{prefix}{with_style(wrapped[0], description_style)}"]
    lines.extend(
        f"{' ' * prefix_width}{with_style(line, description_style)}" for line in wrapped[1:]
    )

    return "\n".join(lines)


def render_command_row(layout: "HelpLayout", command: "Command", ljust: int) -> str:
    """
    Render the listing row for one schema command.

    Args:
        layout (HelpLayout): Layout providing row hooks.
        command (Command): Command to render.
        ljust (int): Name column width.
    """
    if command.obj is not None:
        return layout.get_command_description(command.obj, ljust, command.cli_name, command.aliases)

    command_name = layout._format_command_display_name(command.cli_name, command.aliases)

    return format_command_row(layout, command_name, command.raw_description or "", ljust)


def commands_ljust(layout: "HelpLayout", commands: list["Command"]) -> int:
    """Return the name column width that fits every command's display name."""
    display_names = [
        layout._format_command_display_name(command.cli_name, command.aliases)
        for command in commands
    ]
    max_display = max([len(name) for name in display_names], default=0)

    return layout.get_commands_ljust(max_display)


def partition_commands_by_help_group(
    commands: list["Command"],
) -> tuple[list[str], dict[str, list["Command"]], list["Command"]]:
    """
    Split commands into help groups in first-seen order and ungrouped commands.

    Returns:
        tuple[list[str], dict[str, list[Command]], list[Command]]: Group titles in order,
        commands per group, and commands without a group.
    """
    grouped_command_order: list[str] = []
    grouped_commands: dict[str, list[Command]] = {}
    ungrouped_commands: list[Command] = []
    for command in commands:
        group = command.help_group
        if group is None:
            ungrouped_commands.append(command)
            continue

        if group not in grouped_commands:
            grouped_commands[group] = []
            grouped_command_order.append(group)

        grouped_commands[group].append(command)

    return grouped_command_order, grouped_commands, ungrouped_commands


def render_ungrouped_commands(
    layout: "HelpLayout",
    commands: dict[str, "Command"],
    *,
    rules: list[HelpSubcommandSortRule] | None = None,
) -> str:
    """Render a titled command listing without help groups."""
    ordered_commands = layout.order_commands_for_help(commands, rules=rules)
    ljust = commands_ljust(layout, ordered_commands)
    lines = [layout._format_commands_title()]
    lines.extend(render_command_row(layout, command, ljust) for command in ordered_commands)

    return "\n".join(lines)


def render_grouped_commands(
    layout: "HelpLayout",
    commands: list["Command"],
    *,
    rules: list[HelpSubcommandSortRule] | None = None,
) -> str:
    """Render a command listing with one headed section per help group."""
    group_order, grouped_commands, ungrouped_commands = partition_commands_by_help_group(commands)
    ordered_groups = {
        group: order_command_list(layout, grouped_commands[group], rules=rules)
        for group in group_order
    }
    ordered_ungrouped = order_command_list(layout, ungrouped_commands, rules=rules)

    all_commands: list[Command] = []
    for group in group_order:
        all_commands.extend(ordered_groups[group])

    all_commands.extend(ordered_ungrouped)
    ljust = commands_ljust(layout, all_commands)
    spacing = ["" for _ in range(layout.command_group_spacing)]

    lines: list[str] = []
    for idx, group in enumerate(group_order):
        if idx > 0:
            lines.extend(spacing)

        lines.append(format_command_group_heading(group, layout.style))
        lines.extend(
            render_command_row(layout, command, ljust) for command in ordered_groups[group]
        )

    if ordered_ungrouped:
        if group_order:
            lines.extend(spacing)

        lines.extend(render_command_row(layout, command, ljust) for command in ordered_ungrouped)

    return "\n".join(lines)


def render_command_listing(
    layout: "HelpLayout",
    commands: dict[str, "Command"],
    *,
    rules: list[HelpSubcommandSortRule] | None = None,
) -> str:
    """
    Render a command listing, grouping commands when any has a help group.

    Args:
        layout (HelpLayout): Layout providing row hooks and ordering.
        commands (dict[str, Command]): Commands keyed by name, in insertion order.
        rules (list[HelpSubcommandSortRule] | None): Explicit ordering rules.
    """
    command_list = list(commands.values())
    if not any(command.help_group is not None for command in command_list):
        return render_ungrouped_commands(layout, commands, rules=rules)

    return render_grouped_commands(layout, command_list, rules=rules)


__all__ = [
    "commands_ljust",
    "commands_ljust_width",
    "format_command_display_name",
    "format_command_group_heading",
    "format_command_row",
    "partition_commands_by_help_group",
    "render_command_listing",
    "render_command_row",
    "render_grouped_commands",
    "render_ungrouped_commands",
]

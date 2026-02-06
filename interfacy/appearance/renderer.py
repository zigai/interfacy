from __future__ import annotations

import os
from typing import TYPE_CHECKING

from stdl.st import ansi_len, with_style

if TYPE_CHECKING:
    from interfacy.appearance.layout import HelpLayout
    from interfacy.schema.schema import Argument, Command, ParserSchema


def _get_terminal_width() -> int:
    try:
        return os.get_terminal_size().columns
    except (OSError, AttributeError):
        return 80


def _make_help_argument() -> Argument:
    from interfacy.schema.schema import Argument, ArgumentKind, ValueShape

    return Argument(
        name="help",
        display_name="help",
        kind=ArgumentKind.OPTION,
        value_shape=ValueShape.FLAG,
        flags=("--help",),
        required=False,
        default=None,
        help="show this help message and exit",
        type=None,
        parser=None,
    )


class SchemaHelpRenderer:
    def __init__(
        self,
        layout: HelpLayout,
        terminal_width: int | None = None,
    ) -> None:
        self.layout = layout
        self.terminal_width = terminal_width or _get_terminal_width()

    def render_parser_help(self, schema: ParserSchema, prog: str) -> str:
        if len(schema.commands) == 1:
            cmd = next(iter(schema.commands.values()))
            return self.render_command_help(
                cmd,
                prog,
                parser_description=schema.description,
                parser_epilog=schema.epilog,
            )

        return self._render_multi_command_help(schema, prog)

    def render_command_help(
        self,
        command: Command,
        prog: str,
        *,
        parser_description: str | None = None,
        parser_epilog: str | None = None,
    ) -> str:
        from interfacy.schema.schema import ArgumentKind

        layout = self.layout
        all_args = command.initializer + command.parameters
        positionals = [a for a in all_args if a.kind == ArgumentKind.POSITIONAL]
        options = [a for a in all_args if a.kind == ArgumentKind.OPTION]

        layout.prepare_default_field_width_for_arguments(all_args)

        sections: list[str] = []

        # Usage
        usage = self._build_usage(command, prog)
        sections.append(usage)

        # Description
        description = parser_description or command.description
        if description:
            sections.append(description)

        # Positional arguments
        if positionals:
            heading = self._style_section_heading("positional arguments")
            lines = [heading]
            for arg in positionals:
                rendered = layout.format_argument(arg)
                lines.append(self._indent(rendered))
            sections.append("\n".join(lines))

        # Options
        help_arg = _make_help_argument()
        options_with_help = [help_arg, *options]
        if options_with_help:
            heading = self._style_section_heading("options")
            lines = [heading]
            for arg in options_with_help:
                rendered = layout.format_argument(arg)
                lines.append(self._indent(rendered))
            sections.append("\n".join(lines))

        # Subcommands
        if command.subcommands:
            subcommand_help = layout.get_help_for_multiple_commands(command.subcommands)
            sections.append(subcommand_help)

        # Epilog
        epilog_parts: list[str] = []
        if command.epilog:
            epilog_parts.append(command.epilog)
        if parser_epilog:
            epilog_parts.append(parser_epilog)
        if epilog_parts:
            sections.append("\n\n".join(epilog_parts))

        return "\n\n".join(sections) + "\n"

    def _render_multi_command_help(self, schema: ParserSchema, prog: str) -> str:
        layout = self.layout
        sections: list[str] = []

        # Usage
        usage_prog = self._style_usage_text(prog)
        usage_prefix = self._get_usage_prefix()
        usage = f"{usage_prefix}{usage_prog} [OPTIONS] command [ARGS]"
        sections.append(usage)

        # Description
        if schema.description:
            sections.append(schema.description)

        # Options (--help)
        help_arg = _make_help_argument()
        layout.prepare_default_field_width_for_arguments([help_arg])
        heading = self._style_section_heading("options")
        help_line = layout.format_argument(help_arg)
        sections.append(f"{heading}\n{self._indent(help_line)}")

        # Command listing
        if schema.commands_help:
            sections.append(schema.commands_help)
        elif schema.commands:
            commands_help = layout.get_help_for_multiple_commands(schema.commands)
            sections.append(commands_help)

        # Epilog
        if schema.epilog:
            sections.append(schema.epilog)

        return "\n\n".join(sections) + "\n"

    def _build_usage(self, command: Command, prog: str) -> str:
        from interfacy.schema.schema import ArgumentKind

        all_args = command.initializer + command.parameters
        positionals = [a for a in all_args if a.kind == ArgumentKind.POSITIONAL]
        options = [a for a in all_args if a.kind == ArgumentKind.OPTION]

        usage_prefix = self._get_usage_prefix()

        parts: list[str] = [self._style_usage_text(prog)]

        if options:
            parts.append("[OPTIONS]")

        for arg in positionals:
            name = (arg.metavar or arg.name or "arg").upper()
            if arg.required:
                parts.append(name)
            else:
                parts.append(f"[{name}]")

        if command.subcommands:
            parts.append("{command}")

        usage_text = " ".join(parts)

        text_width = self.terminal_width
        prefix_len = ansi_len(usage_prefix)
        if prefix_len + ansi_len(usage_text) > text_width:
            indent = " " * prefix_len
            wrapped = self._wrap_usage_parts(parts, text_width, prefix_len, indent)
            return f"{usage_prefix}{wrapped}"

        return f"{usage_prefix}{usage_text}"

    def _wrap_usage_parts(
        self,
        parts: list[str],
        text_width: int,
        prefix_len: int,
        indent: str,
    ) -> str:
        lines: list[str] = []
        current_line: list[str] = []
        current_len = prefix_len

        for part in parts:
            part_len = ansi_len(part)
            if current_line and current_len + 1 + part_len > text_width:
                lines.append(" ".join(current_line))
                current_line = [part]
                current_len = len(indent) + part_len
            else:
                current_line.append(part)
                current_len += part_len + (1 if len(current_line) > 1 else 0)

        if current_line:
            lines.append(" ".join(current_line))

        if len(lines) <= 1:
            return lines[0] if lines else ""
        return lines[0] + "\n" + "\n".join(indent + line for line in lines[1:])

    def _get_usage_prefix(self) -> str:
        layout = self.layout
        prefix = layout.usage_prefix or "usage: "
        if layout.usage_style is not None:
            prefix = with_style(prefix, layout.usage_style)
        return prefix

    def _style_usage_text(self, text: str) -> str:
        if self.layout.usage_text_style is not None:
            return with_style(text, self.layout.usage_text_style)
        return text

    def _style_section_heading(self, heading: str) -> str:
        layout = self.layout
        title_map = layout.section_title_map
        if title_map is not None:
            heading_key = heading.rstrip(":").strip().lower()
            mapped = title_map.get(heading) or title_map.get(heading_key)
            if mapped:
                heading = mapped
        if layout.section_heading_style is not None:
            heading = with_style(heading, layout.section_heading_style)
        return heading + ":"

    def _indent(self, text: str, width: int = 2) -> str:
        prefix = " " * width
        lines = text.splitlines()
        return "\n".join(prefix + line for line in lines)


__all__ = ["SchemaHelpRenderer"]

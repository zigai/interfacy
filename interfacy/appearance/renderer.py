from __future__ import annotations

import os
import re

from stdl.st import ansi_len, with_style

from interfacy.appearance.layout import HelpLayout
from interfacy.schema.schema import Argument, ArgumentKind, Command, ParserSchema, ValueShape


def _get_terminal_width() -> int:
    try:
        return os.get_terminal_size().columns
    except (OSError, AttributeError):
        return 80


def _make_help_argument(help_text: str) -> Argument:
    return Argument(
        name="help",
        display_name="help",
        kind=ArgumentKind.OPTION,
        value_shape=ValueShape.FLAG,
        flags=("--help",),
        required=False,
        default=None,
        help=help_text,
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
            if cmd.is_leaf:
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
        layout = self.layout
        all_args = command.initializer + command.parameters
        positionals = [a for a in all_args if a.kind == ArgumentKind.POSITIONAL]
        options = [a for a in all_args if a.kind == ArgumentKind.OPTION]

        layout.prepare_default_field_width_for_arguments(all_args)

        sections: list[str] = []
        usage = self._build_usage(command, prog)
        sections.append(usage)
        description = parser_description or command.description

        if description:
            sections.append(description)

        if positionals:
            heading = self._style_section_heading("positional arguments")
            lines = [heading]
            for arg in positionals:
                rendered = layout.format_argument(arg)
                lines.append(self._indent(rendered))
            sections.append("\n".join(lines))

        help_arg = _make_help_argument(layout.help_option_description)
        options_with_help = [help_arg, *options]

        if options_with_help:
            heading = self._style_section_heading("options")
            lines = [heading]
            help_only_section = not options
            for arg in options_with_help:
                rendered = layout.format_argument(arg)
                if help_only_section and arg.name == "help":
                    rendered = self._normalize_help_only_option_line(rendered)
                lines.append(self._indent(rendered))
            sections.append("\n".join(lines))

        if command.subcommands:
            subcommand_help = layout.get_help_for_multiple_commands(command.subcommands)
            sections.append(subcommand_help)

        epilog_parts: list[str] = []
        if command.epilog:
            normalized_epilog = re.sub(r"\x1b\[[0-9;]*m", "", command.epilog)
            is_legacy_command_epilog = (
                command.subcommands is not None
                and normalized_epilog.lstrip().lower().startswith("commands:")
            )
            if not is_legacy_command_epilog:
                epilog_parts.append(command.epilog)
        if parser_epilog:
            epilog_parts.append(parser_epilog)
        if epilog_parts:
            sections.append("\n\n".join(epilog_parts))

        return "\n\n".join(sections) + "\n"

    def _render_multi_command_help(self, schema: ParserSchema, prog: str) -> str:
        layout = self.layout
        sections: list[str] = []
        usage_prog = self._style_usage_text(self._normalize_prog(prog))
        usage_prefix = self._get_usage_prefix()
        usage = f"{usage_prefix}{usage_prog} {layout.get_parser_command_usage_suffix()}"

        sections.append(usage)
        if schema.description:
            sections.append(schema.description)

        help_arg = _make_help_argument(layout.help_option_description)
        layout.prepare_default_field_width_for_arguments([help_arg])
        heading = self._style_section_heading("options")
        help_line = self._normalize_help_only_option_line(layout.format_argument(help_arg))
        sections.append(f"{heading}\n{self._indent(help_line)}")

        if schema.commands_help:
            sections.append(schema.commands_help)
        elif schema.commands:
            commands_help = layout.get_help_for_multiple_commands(schema.commands)
            sections.append(commands_help)
        if schema.epilog:
            sections.append(schema.epilog)

        return "\n\n".join(sections) + "\n"

    def _build_usage(self, command: Command, prog: str) -> str:
        all_args = command.initializer + command.parameters
        positionals = [a for a in all_args if a.kind == ArgumentKind.POSITIONAL]
        options = [a for a in all_args if a.kind == ArgumentKind.OPTION]
        compact_options_usage = self.layout.compact_options_usage

        usage_prefix = self._get_usage_prefix()

        parts: list[str] = [self._style_usage_text(self._normalize_prog(prog))]
        if compact_options_usage:
            parts.append("[OPTIONS]")
            for arg in options:
                if arg.required:
                    parts.append(self._usage_token_for_option(arg, compact_style=True))
        else:
            parts.append("[--help]")
            for arg in options:
                parts.append(self._usage_token_for_option(arg))

        for arg in positionals:
            raw_name = arg.metavar
            if raw_name is None or "\b" in raw_name:
                raw_name = arg.display_name or arg.name or "arg"
            name = raw_name.upper()
            metavar_name = self.layout.format_usage_metavar(name, is_varargs=False)
            if arg.value_shape == ValueShape.LIST:
                token = (
                    self.layout.format_usage_metavar(name, is_varargs=True)
                    if compact_options_usage
                    else f"{name} ..."
                )
                parts.append(token if arg.nargs == "+" else f"[{token}]")
                continue
            if arg.value_shape == ValueShape.TUPLE and isinstance(arg.nargs, int) and arg.nargs > 1:
                token_atom = metavar_name if compact_options_usage else name
                token = " ".join([token_atom] * arg.nargs)
                parts.append(token if arg.required else f"[{token}]")
                continue
            token = metavar_name if compact_options_usage else name
            parts.append(token if arg.required else f"[{token}]")

        if command.subcommands:
            parts.append(self._usage_token_for_subcommands(command))

        usage_text = " ".join(parts)

        text_width = self.terminal_width
        prefix_len = ansi_len(usage_prefix)
        if prefix_len + ansi_len(usage_text) > text_width:
            indent = " " * prefix_len
            wrapped = self._wrap_usage_parts(parts, text_width, prefix_len, indent)
            return f"{usage_prefix}{wrapped}"

        return f"{usage_prefix}{usage_text}"

    def _usage_token_for_subcommands(self, command: Command) -> str:
        token = self.layout.get_subcommand_usage_token()
        if "{command}" not in token or not command.subcommands:
            return token

        choices = [subcommand.cli_name for subcommand in command.subcommands.values()]
        if not choices:
            return token
        return token.replace("{command}", "{" + ",".join(choices) + "}")

    def _usage_token_for_option(self, arg: Argument, *, compact_style: bool = False) -> str:
        longs = [flag for flag in arg.flags if flag.startswith("--")]
        shorts = [flag for flag in arg.flags if flag.startswith("-") and not flag.startswith("--")]
        primary_flag = longs[0] if longs else (shorts[0] if shorts else f"--{arg.display_name}")

        is_bool = self.layout._arg_is_bool(arg)
        if is_bool:
            primary_bool = self.layout._get_primary_boolean_flag_from_argument(arg) or primary_flag
            return primary_bool if arg.required else f"[{primary_bool}]"

        raw_metavar = arg.metavar
        if raw_metavar is None or "\b" in raw_metavar:
            raw_metavar = arg.display_name or arg.name or "value"

        metavar = raw_metavar.upper()
        if arg.value_shape == ValueShape.LIST:
            if compact_style:
                value_token = self.layout.format_usage_metavar(metavar, is_varargs=True)
            else:
                value_token = f"[{metavar} ...]"
        elif arg.value_shape == ValueShape.TUPLE and isinstance(arg.nargs, int) and arg.nargs > 1:
            atom = (
                self.layout.format_usage_metavar(metavar, is_varargs=False)
                if compact_style
                else metavar
            )
            value_token = " ".join([atom] * arg.nargs)
        else:
            value_token = (
                self.layout.format_usage_metavar(metavar, is_varargs=False)
                if compact_style
                else metavar
            )

        token = f"{primary_flag} {value_token}"
        return token if arg.required else f"[{token}]"

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

    def _normalize_prog(self, prog: str) -> str:
        return re.sub(
            r"^(?:\x1b\[[0-9;]*m)*\s*usage:\s*",
            "",
            prog,
            flags=re.IGNORECASE,
        ).strip()

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

    @staticmethod
    def _normalize_help_only_option_line(line: str) -> str:
        """Normalize synthetic help-only rows for aligned layouts."""
        return re.sub(r"^\s+(--help\b)", r"\1", line)


__all__ = ["SchemaHelpRenderer"]

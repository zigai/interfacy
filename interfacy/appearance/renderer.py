from __future__ import annotations

import re
from dataclasses import replace

from stdl.st import ansi_len, with_style

from interfacy.appearance.layout import HelpLayout
from interfacy.schema.schema import Argument, ArgumentKind, Command, ParserSchema, ValueShape
from interfacy.util import get_terminal_width

_DEFAULT_HELP_ARGUMENT = object()


def _make_help_argument(
    help_text: str,
    *,
    flags: tuple[str, ...] = ("--help",),
) -> Argument:
    return Argument(
        name="help",
        display_name="help",
        kind=ArgumentKind.OPTION,
        value_shape=ValueShape.FLAG,
        flags=flags,
        required=False,
        default=None,
        help=help_text,
        type=None,
        parser=None,
        is_help_action=True,
    )


def has_grouped_commands(commands: dict[str, Command] | None) -> bool:
    """Return whether any command in a mapping has a help-group label."""
    if not commands:
        return False
    return any(command.help_group is not None for command in commands.values())


def command_has_grouped_subcommands(command: Command | None) -> bool:
    """Return whether a command has subcommands with help-group labels."""
    if command is None:
        return False
    return has_grouped_commands(command.subcommands)


class SchemaHelpRenderer:
    """
    Render parser and command help text from schema objects.

    Attributes:
        layout (HelpLayout): Active help layout used for formatting.
        terminal_width (int): Target terminal width in columns.
    """

    def __init__(
        self,
        layout: HelpLayout,
        terminal_width: int | None = None,
        help_argument: Argument | None | object = _DEFAULT_HELP_ARGUMENT,
    ) -> None:
        self.layout = layout
        self.terminal_width = terminal_width or get_terminal_width()
        self._help_argument = help_argument

    def render_parser_help(self, schema: ParserSchema, prog: str) -> str:
        """
        Render help text for a parser schema and program name.

        Args:
            schema (ParserSchema): Parser schema to render.
            prog (str): Program name or invocation prefix.
        """
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
        """
        Render help text for one command schema.

        Args:
            command (Command): Command schema to render.
            prog (str): Program name or invocation prefix.
            parser_description (str | None): Optional parser-level description override.
            parser_epilog (str | None): Optional parser-level epilog text.
        """
        layout = self.layout
        all_args = command.initializer + command.parameters
        positionals = [a for a in all_args if a.kind == ArgumentKind.POSITIONAL]
        options = [a for a in all_args if a.kind == ArgumentKind.OPTION]
        options = layout.order_option_arguments_for_help(
            options,
            rules=command.help_option_sort_effective,
        )
        help_arg = self._get_help_argument()

        layout.prepare_default_field_width_for_arguments(
            [*([help_arg] if help_arg is not None else []), *all_args]
        )

        sections: list[str] = []
        usage = self._build_usage(command, prog)
        description = parser_description or command.description
        self._append_usage_and_description(sections=sections, usage=usage, description=description)

        positionals_section = self._render_argument_section("positional arguments", positionals)
        if positionals_section is not None:
            sections.append(positionals_section)

        options_with_help = [*([help_arg] if help_arg is not None else []), *options]
        options_section = self._render_argument_section(
            "options",
            options_with_help,
            normalize_help_only=help_arg is not None and not options,
        )
        if options_section is not None:
            sections.append(options_section)

        if command.subcommands:
            subcommand_help = layout.get_help_for_multiple_commands(
                command.subcommands,
                rules=command.help_subcommand_sort_effective,
            )
            sections.append(subcommand_help)

        epilog_block = self._build_epilog_block(command, parser_epilog)
        if epilog_block is not None:
            sections.append(epilog_block)

        return "\n\n".join(sections) + "\n"

    def _append_usage_and_description(
        self,
        *,
        sections: list[str],
        usage: str,
        description: str | None,
    ) -> None:
        if self.layout.should_render_description_before_usage():
            if description:
                sections.append(description)
            sections.append(usage)
            return

        sections.append(usage)
        if description:
            sections.append(description)

    def _render_argument_section(
        self,
        heading: str,
        arguments: list[Argument],
        *,
        normalize_help_only: bool = False,
    ) -> str | None:
        if not arguments:
            return None

        previous_keep = self.layout.keep_empty_default_slot_for_help
        self.layout.keep_empty_default_slot_for_help = (
            self.layout.keep_help_default_slot_for_arguments(arguments)
        )
        lines = [self._style_section_heading(heading)]
        try:
            for arg in arguments:
                rendered = self.layout.format_argument(arg)
                if normalize_help_only and arg.is_help_action:
                    rendered = self._normalize_help_only_option_line(rendered, arg)
                lines.append(self._indent(rendered))
        finally:
            self.layout.keep_empty_default_slot_for_help = previous_keep
        return "\n".join(lines)

    def _build_epilog_block(self, command: Command, parser_epilog: str | None) -> str | None:
        epilog_parts: list[str] = []
        if command.epilog:
            normalized_epilog = re.sub(r"\x1b\[[0-9;]*m", "", command.epilog).strip()
            is_generated_subcommand_epilog = False
            if command.subcommands is not None:
                generated_subcommand_help = self.layout.get_help_for_multiple_commands(
                    command.subcommands,
                    rules=command.help_subcommand_sort_effective,
                )
                normalized_generated_help = re.sub(
                    r"\x1b\[[0-9;]*m",
                    "",
                    generated_subcommand_help,
                ).strip()
                is_generated_subcommand_epilog = (
                    normalized_epilog.lower().startswith("commands:")
                    or normalized_epilog == normalized_generated_help
                )

            if not is_generated_subcommand_epilog:
                epilog_parts.append(command.epilog)
        if parser_epilog:
            epilog_parts.append(parser_epilog)
        if not epilog_parts:
            return None
        return "\n\n".join(epilog_parts)

    def _render_multi_command_help(self, schema: ParserSchema, prog: str) -> str:
        layout = self.layout
        sections: list[str] = []
        usage_prog = self._style_usage_text(self._normalize_prog(prog))
        usage_prefix = self._get_usage_prefix()
        usage = f"{usage_prefix}{usage_prog} {layout.get_parser_command_usage_suffix()}"

        if layout.should_render_description_before_usage():
            if schema.description:
                sections.append(schema.description)
            sections.append(usage)
        else:
            sections.append(usage)
            if schema.description:
                sections.append(schema.description)

        help_arg = self._get_help_argument()
        if help_arg is not None:
            layout.prepare_default_field_width_for_arguments([help_arg])
            heading = self._style_section_heading("options")
            help_line = self._normalize_help_only_option_line(
                layout.format_argument(help_arg), help_arg
            )
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
        options = self.layout.order_option_arguments_for_help(
            options,
            rules=command.help_option_sort_effective,
        )
        compact_options_usage = self.layout.compact_options_usage

        usage_prefix = self._get_usage_prefix()

        parts: list[str] = [self._style_usage_text(self._normalize_prog(prog))]
        if compact_options_usage:
            parts.append("[OPTIONS]")
            parts.extend(
                self._usage_token_for_option(arg, compact_style=True)
                for arg in options
                if arg.required
            )
        else:
            help_arg = self._get_help_argument()
            if help_arg is not None:
                parts.append(self._usage_token_for_option(help_arg))
            parts.extend(self._usage_token_for_option(arg) for arg in options)

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

        ordered_subcommands = self.layout.order_commands_for_help(
            command.subcommands,
            rules=command.help_subcommand_sort_effective,
        )
        choices = [subcommand.cli_name for subcommand in ordered_subcommands]
        if not choices:
            return token
        return token.replace("{command}", "{" + ",".join(choices) + "}")

    def _usage_token_for_option(self, arg: Argument, *, compact_style: bool = False) -> str:
        longs = [flag for flag in arg.flags if len(flag) > 2]
        shorts = [flag for flag in arg.flags if len(flag) <= 2]
        primary_flag = longs[0] if longs else (shorts[0] if shorts else f"--{arg.display_name}")

        is_bool = self.layout.is_argument_boolean(arg)
        if is_bool:
            primary_bool = self.layout.get_primary_boolean_flag_for_argument(arg) or primary_flag
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

    def _get_help_argument(self) -> Argument | None:
        if self._help_argument is _DEFAULT_HELP_ARGUMENT:
            return _make_help_argument(self.layout.help_option_description)
        if self._help_argument is None:
            return None
        return replace(
            self._help_argument,
            help=self.layout.help_option_description,
            is_help_action=True,
        )

    def _normalize_help_only_option_line(self, line: str, help_arg: Argument) -> str:
        """Normalize synthetic help-only rows so the configured help flag stays visible."""
        normalized = line.lstrip()
        if any(flag and flag in normalized for flag in help_arg.flags):
            return normalized

        description = line.strip()
        primary_flag = self.layout.get_primary_boolean_flag_for_argument(help_arg) or (
            help_arg.flags[0] if help_arg.flags else "--help"
        )
        if not description:
            return primary_flag

        help_position = self.layout.help_position
        padding = max(2, help_position - len(primary_flag)) if help_position is not None else 2
        return f"{primary_flag}{' ' * padding}{description}"


__all__ = [
    "SchemaHelpRenderer",
    "command_has_grouped_subcommands",
    "has_grouped_commands",
]

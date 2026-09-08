from __future__ import annotations

import re
import textwrap
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import replace
from typing import Any

from stdl.st import ansi_len, with_style

from interfacy.executable_flag import ExecutableFlag, executable_flag_to_argument
from interfacy.help.content import (
    HelpContent,
    HelpContext,
    HelpRenderer,
    HelpSection,
    render_help_content,
)
from interfacy.help.layout import HelpLayout
from interfacy.help.terminal import get_terminal_width
from interfacy.help.wrapping import wrap_usage_parts
from interfacy.schema.schema import (
    Argument,
    ArgumentDefault,
    ArgumentKind,
    Command,
    ParserSchema,
    ValueCardinality,
    ValueShape,
)

_DEFAULT_HELP_ARGUMENT = object()
_USAGE_PREFIX_RE = re.compile(r"^(?:\x1b\[[0-9;]*m)*\s*usage:\s*", flags=re.IGNORECASE)


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
        cardinality=ValueCardinality(0, 0, 0),
        argument_default=ArgumentDefault.present(None, suppress_help_default=True),
        help=help_text,
        type=None,
        parser=None,
        is_help_action=True,
    )


def has_grouped_commands(commands: dict[str, Command] | None) -> bool:
    """Return whether any command in a mapping has a help-group label."""
    return bool(commands and any(command.help_group is not None for command in commands.values()))


def command_has_grouped_subcommands(command: Command | None) -> bool:
    """Return whether a command has subcommands with help-group labels."""
    return bool(command and has_grouped_commands(command.subcommands))


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
        help_argument: Argument | Any | None = _DEFAULT_HELP_ARGUMENT,
        help_flags: tuple[str, ...] = ("--help",),
        final_renderer: HelpRenderer | None = None,
    ) -> None:
        self.layout = layout
        self._configured_terminal_width = terminal_width
        self._render_width: int | None = None
        self._render_layout_source: HelpLayout | None = None
        self._help_argument = help_argument
        self._help_flags = help_flags
        self._final_renderer = final_renderer

    @property
    def terminal_width(self) -> int:
        if self._render_width is not None:
            return self._render_width

        return self._configured_terminal_width or get_terminal_width()

    @terminal_width.setter
    def terminal_width(self, value: int | None) -> None:
        self._configured_terminal_width = value

    def render_parser_help(self, schema: ParserSchema, prog: str) -> str:
        """
        Render help text for a parser schema and program name.

        Args:
            schema (ParserSchema): Parser schema to render.
            prog (str): Program name or invocation prefix.
        """
        with self._render_scope():
            previous_help_argument = self._help_argument
            if previous_help_argument is _DEFAULT_HELP_ARGUMENT:
                self._help_argument = _make_help_argument(
                    self.layout.help_option_description,
                    flags=schema.help_flags,
                )

            try:
                if len(schema.commands) == 1:
                    cmd = next(iter(schema.commands.values()))
                    return self.render_command_help(
                        cmd,
                        prog,
                        parser_description=schema.description,
                        parser_epilog=schema.epilog,
                        parser_executable_flags=schema.executable_flags,
                        parser_schema=schema,
                    )

                return self._render_multi_command_help(schema, prog)
            finally:
                self._help_argument = previous_help_argument

    def render_command_help(
        self,
        command: Command,
        prog: str,
        *,
        parser_description: str | None = None,
        parser_epilog: str | None = None,
        parser_executable_flags: list[ExecutableFlag] | None = None,
        parser_schema: ParserSchema | None = None,
    ) -> str:
        """
        Render help text for one command schema.

        Args:
            command (Command): Command schema to render.
            prog (str): Program name or invocation prefix.
            parser_description (str | None): Optional parser-level description override.
            parser_epilog (str | None): Optional parser-level epilog text.
            parser_executable_flags (list[ExecutableFlag] | None): Parser-level executable
                flags to merge into single-command help output.
            parser_schema (ParserSchema | None): Parser schema owning the rendered command.
        """
        with self._render_scope():
            layout = self.layout
            all_args = command.initializer + command.parameters
            positionals = [a for a in all_args if a.kind == ArgumentKind.POSITIONAL]
            options = self._ordered_option_arguments(
                [a for a in all_args if a.kind == ArgumentKind.OPTION],
                command.executable_flags,
                parser_executable_flags=parser_executable_flags,
                rules=command.help_option_sort_effective,
            )
            help_arg = self._get_help_argument()

            layout.prepare_default_field_width_for_arguments(
                [*([help_arg] if help_arg is not None else []), *positionals, *options]
            )

            sections: list[HelpSection] = []
            usage = self._build_usage(
                command, prog, parser_executable_flags=parser_executable_flags
            )
            description = parser_description or command.description
            self._append_usage_and_description(
                sections=sections, usage=usage, description=description
            )

            positionals_section = self._render_argument_section("positional arguments", positionals)
            if positionals_section is not None:
                sections.append(HelpSection("positionals", positionals_section))

            options_with_help = [*([help_arg] if help_arg is not None else []), *options]
            options_section = self._render_argument_section(
                "options",
                options_with_help,
                normalize_help_only=help_arg is not None and not options,
            )
            if options_section is not None:
                sections.append(HelpSection("options", options_section))

            if command.subcommands:
                subcommand_help = layout.get_help_for_multiple_commands(
                    command.subcommands,
                    rules=command.help_subcommand_sort_effective,
                )
                sections.append(HelpSection("commands", subcommand_help))

            epilog_block = self._build_epilog_block(command, parser_epilog)
            if epilog_block is not None:
                sections.append(HelpSection("epilog", epilog_block))

            context = HelpContext(
                prog=prog,
                terminal_width=self.terminal_width,
                schema=parser_schema,
                command=command,
            )

            return self._render_content(context, sections)

    @contextmanager
    def _render_scope(self) -> Generator[None, None, None]:
        previous_layout = self.layout
        previous_source = self._render_layout_source
        previous_width = self._render_width
        source = previous_source if previous_source is not None else previous_layout
        width = self.terminal_width
        layout = source._for_render(width)
        self.layout = layout
        self._render_layout_source = source
        self._render_width = width
        try:
            yield
        finally:
            self.layout = previous_layout
            self._render_layout_source = previous_source
            self._render_width = previous_width

    def _append_usage_and_description(
        self,
        *,
        sections: list[HelpSection],
        usage: str,
        description: str | None,
    ) -> None:
        rendered_description = self._wrap_description(description)
        if self.layout.should_render_description_before_usage():
            if rendered_description:
                sections.append(HelpSection("description", rendered_description))

            sections.append(HelpSection("usage", usage))

            return

        sections.append(HelpSection("usage", usage))
        if rendered_description:
            sections.append(HelpSection("description", rendered_description))

    def _wrap_description(self, description: str | None) -> str | None:
        if not description:
            return None

        formatted = self.layout.format_description(description)
        paragraphs = formatted.splitlines()
        if not paragraphs:
            return None

        wrapped: list[str] = []
        for paragraph in paragraphs:
            if not paragraph.strip():
                wrapped.append("")
                continue

            wrapped.append(
                textwrap.fill(
                    paragraph.strip(),
                    width=max(10, self.terminal_width),
                    break_long_words=False,
                    break_on_hyphens=False,
                )
            )

        return "\n".join(wrapped)

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
        previous_help_position = self.layout.help_position
        self.layout.keep_empty_default_slot_for_help = (
            self.layout.keep_help_default_slot_for_arguments(arguments)
        )
        if not self.layout._use_template_layout():
            base_position = (
                previous_help_position if isinstance(previous_help_position, int) else 32
            )
            widest_flag = max(
                ansi_len(self.layout._adaptive_argument_flag(argument)) for argument in arguments
            )
            self.layout.help_position = max(base_position, widest_flag + 2)
        lines = [self._style_section_heading(heading)]
        try:
            for arg in arguments:
                if self.layout._use_template_layout():
                    rendered = self.layout.format_argument(arg)
                else:
                    rendered = self.layout.format_adaptive_argument_row(arg)

                if normalize_help_only and arg.is_help_action:
                    rendered = self._normalize_help_only_option_line(rendered, arg)
                lines.append(self._indent(rendered))
        finally:
            self.layout.keep_empty_default_slot_for_help = previous_keep
            self.layout.help_position = previous_help_position

        return "\n".join(lines)

    @staticmethod
    def _build_epilog_block(
        command: Command,
        parser_epilog: str | None,
    ) -> str | None:
        parts = [p for p in (command.epilog, parser_epilog) if p]
        return "\n\n".join(parts) or None

    def _render_multi_command_help(self, schema: ParserSchema, prog: str) -> str:
        layout = self.layout
        sections: list[HelpSection] = []
        usage_prog = self._style_usage_text(self._normalize_prog(prog))
        usage_prefix = self._get_usage_prefix()
        usage_suffix = self._usage_token_for_commands(
            schema.commands,
            rules=schema.help_subcommand_sort_effective,
            fallback=layout.get_parser_command_usage_suffix(),
        )
        usage_text = f"{usage_prog} {usage_suffix}"
        usage_prefix_len = ansi_len(usage_prefix)
        if usage_prefix_len + ansi_len(usage_text) > self.terminal_width:
            wrapped_usage = wrap_usage_parts(
                [usage_prog, usage_suffix],
                width=self.terminal_width,
                prefix_width=usage_prefix_len,
                indent=" " * usage_prefix_len,
            )
            usage = f"{usage_prefix}{wrapped_usage}"
        else:
            usage = f"{usage_prefix}{usage_text}"

        self._append_usage_and_description(
            sections=sections,
            usage=usage,
            description=schema.description,
        )

        help_arg = self._get_help_argument()
        root_options = self._ordered_option_arguments(
            [],
            schema.executable_flags,
            rules=schema.help_option_sort_effective,
        )
        root_options_with_help = [*([help_arg] if help_arg is not None else []), *root_options]
        if root_options_with_help:
            layout.prepare_default_field_width_for_arguments(root_options_with_help)
            options = self._render_argument_section(
                "options",
                root_options_with_help,
                normalize_help_only=help_arg is not None and not root_options,
            )
            if options is not None:
                sections.append(HelpSection("options", options))

        if schema.commands:
            commands = layout.get_help_for_multiple_commands(schema.commands)
            sections.append(HelpSection("commands", commands))

        if schema.epilog:
            sections.append(HelpSection("epilog", schema.epilog))

        context = HelpContext(
            prog=prog,
            terminal_width=self.terminal_width,
            schema=schema,
        )

        return self._render_content(context, sections)

    def _render_content(
        self,
        context: HelpContext,
        sections: list[HelpSection],
    ) -> str:
        content = HelpContent(tuple(sections))
        return render_help_content(context, content, self._final_renderer)

    def _build_usage(
        self,
        command: Command,
        prog: str,
        *,
        parser_executable_flags: list[ExecutableFlag] | None = None,
    ) -> str:
        all_args = command.initializer + command.parameters
        positionals = [a for a in all_args if a.kind == ArgumentKind.POSITIONAL]
        options = self._ordered_option_arguments(
            [a for a in all_args if a.kind == ArgumentKind.OPTION],
            command.executable_flags,
            parser_executable_flags=parser_executable_flags,
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
                parts.append(token if arg.cardinality.minimum_values > 0 else f"[{token}]")
                continue

            if arg.value_shape == ValueShape.TUPLE and arg.cardinality.group_size > 1:
                token_atom = metavar_name if compact_options_usage else name
                token = " ".join([token_atom] * arg.cardinality.group_size)
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
            wrapped = wrap_usage_parts(
                parts, width=text_width, prefix_width=prefix_len, indent=indent
            )
            return f"{usage_prefix}{wrapped}"

        return f"{usage_prefix}{usage_text}"

    def _ordered_option_arguments(
        self,
        options: list[Argument],
        executable_flags: list[ExecutableFlag],
        *,
        parser_executable_flags: list[ExecutableFlag] | None = None,
        rules: list[Any] | None = None,
    ) -> list[Argument]:
        flag_arguments = [
            executable_flag_to_argument(flag)
            for flag in [*(parser_executable_flags or []), *executable_flags]
        ]
        return self.layout.order_option_arguments_for_help(
            [*options, *flag_arguments],
            rules=rules,
        )

    def _usage_token_for_subcommands(self, command: Command) -> str:
        return self._usage_token_for_commands(
            command.subcommands or {},
            rules=command.help_subcommand_sort_effective,
            fallback=self.layout.get_subcommand_usage_token(),
        )

    def _usage_token_for_commands(
        self,
        commands: dict[str, Command],
        *,
        rules: list[Any] | None,
        fallback: str,
    ) -> str:
        if "{command}" not in fallback or not commands:
            return fallback

        ordered_subcommands = self.layout.order_commands_for_help(
            commands,
            rules=rules,
        )
        choices = [subcommand.cli_name for subcommand in ordered_subcommands]
        if not choices:
            return fallback

        return fallback.replace("{command}", "{" + ",".join(choices) + "}")

    def _usage_token_for_option(self, arg: Argument, *, compact_style: bool = False) -> str:
        longs = [flag for flag in arg.flags if len(flag) > 2]
        shorts = [flag for flag in arg.flags if len(flag) <= 2]
        primary_flag = shorts[0] if shorts else (longs[0] if longs else f"--{arg.display_name}")

        is_bool = self.layout.is_argument_boolean(arg)
        if is_bool:
            primary_bool = self.layout.get_primary_boolean_flag_for_argument(arg) or primary_flag
            return primary_bool if arg.required else f"[{primary_bool}]"

        if self.layout.clear_metavar:
            return primary_flag if arg.required else f"[{primary_flag}]"

        raw_metavar = arg.metavar
        if raw_metavar is None or "\b" in raw_metavar:
            raw_metavar = arg.display_name or arg.name or "value"

        metavar = raw_metavar.upper()
        if arg.value_shape == ValueShape.LIST:
            if compact_style:
                value_token = self.layout.format_usage_metavar(metavar, is_varargs=True)
            else:
                value_token = f"[{metavar} ...]"
        elif arg.value_shape == ValueShape.TUPLE and arg.cardinality.group_size > 1:
            atom = (
                self.layout.format_usage_metavar(metavar, is_varargs=False)
                if compact_style
                else metavar
            )
            value_token = " ".join([atom] * arg.cardinality.group_size)
        else:
            value_token = (
                self.layout.format_usage_metavar(metavar, is_varargs=False)
                if compact_style
                else metavar
            )

        token = f"{primary_flag} {value_token}"

        return token if arg.required else f"[{token}]"

    def _get_usage_prefix(self) -> str:
        layout = self.layout
        prefix = layout.usage_prefix or "usage: "
        if layout.style.usage_style is not None:
            prefix = with_style(prefix, layout.style.usage_style)

        return prefix

    def _normalize_prog(self, prog: str) -> str:
        return _USAGE_PREFIX_RE.sub("", prog).strip()

    def _style_usage_text(self, text: str) -> str:
        if self.layout.style.usage_text_style is not None:
            return with_style(text, self.layout.style.usage_text_style)

        return text

    def _style_section_heading(self, heading: str) -> str:
        layout = self.layout
        title_map = layout.section_title_map
        if title_map is not None:
            heading_key = heading.rstrip(":").strip().lower()
            mapped = title_map.get(heading) or title_map.get(heading_key)
            if mapped:
                heading = mapped

        if layout.style.section_heading_style is not None:
            heading = with_style(heading, layout.style.section_heading_style)

        return heading + ":"

    def _indent(self, text: str, width: int = 2) -> str:
        prefix = " " * width
        lines: list[str] = []
        for line in text.splitlines():
            indented = prefix + line
            if ansi_len(indented) <= self.terminal_width:
                lines.append(indented)
                continue

            leading = len(indented) - len(indented.lstrip(" "))
            wrap_indent = " " * (leading if leading < self.terminal_width - 10 else width)
            lines.extend(
                textwrap.wrap(
                    indented.strip(),
                    width=max(10, self.terminal_width),
                    initial_indent=wrap_indent,
                    subsequent_indent=wrap_indent,
                    break_long_words=True,
                    break_on_hyphens=False,
                )
            )

        return "\n".join(lines)

    def _get_help_argument(self) -> Argument | None:
        if self._help_argument is _DEFAULT_HELP_ARGUMENT:
            return _make_help_argument(
                self.layout.help_option_description,
                flags=self._help_flags,
            )
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
        removed = len(line) - len(normalized)
        if removed and "\n" in normalized:
            normalized_lines = normalized.splitlines()
            dedented = [normalized_lines[0]]
            for continuation in normalized_lines[1:]:
                leading = len(continuation) - len(continuation.lstrip(" "))
                dedented.append(continuation[min(removed, leading) :])

            normalized = "\n".join(dedented)

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

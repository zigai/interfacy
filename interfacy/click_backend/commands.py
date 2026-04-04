from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import click
from click.formatting import iter_rows, measure_table, term_len, wrap_text

from interfacy.appearance.renderer import (
    SchemaHelpRenderer,
    command_has_grouped_subcommands,
    has_grouped_commands,
)
from interfacy.click_backend.parser import InterfacyOptionParser

if TYPE_CHECKING:
    from interfacy.schema.schema import Argument, Command, ParserSchema


def _uses_template_layout(layout: object) -> bool:
    layout_mode = getattr(layout, "layout_mode", None)
    if layout_mode == "template":
        return True
    if layout_mode == "adaptive":
        return False
    return bool(
        getattr(layout, "format_option", None) or getattr(layout, "format_positional", None)
    )


class InterfacyClickHelpFormatter(click.HelpFormatter):
    """Click formatter that can pin help descriptions to an absolute column."""

    def __init__(
        self,
        *,
        help_position: int | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.interfacy_help_position = help_position

    def write_dl(
        self,
        rows: Sequence[tuple[str, str]],
        col_max: int = 30,
        col_spacing: int = 2,
    ) -> None:
        target = self.interfacy_help_position
        if target is None:
            super().write_dl(rows, col_max=col_max, col_spacing=col_spacing)
            return

        rows = list(rows)
        widths = measure_table(rows)
        if len(widths) != 2:
            msg = "Expected two columns for definition list"
            raise TypeError(msg)

        first_col = max(col_spacing, target - self.current_indent)

        for first, second in iter_rows(rows, len(widths)):
            self.write(f"{'':>{self.current_indent}}{first}")
            if not second:
                self.write("\n")
                continue
            if term_len(first) <= first_col - col_spacing:
                self.write(" " * (first_col - term_len(first)))
            else:
                self.write("\n")
                self.write(" " * (first_col + self.current_indent))

            text_width = max(self.width - first_col - 2, 10)
            wrapped_text = wrap_text(second, text_width, preserve_paragraphs=True)
            lines = wrapped_text.splitlines()

            if lines:
                self.write(f"{lines[0]}\n")
                for line in lines[1:]:
                    self.write(f"{'':>{first_col + self.current_indent}}{line}\n")
            else:
                self.write("\n")


class InterfacyClickOption(click.Option):
    """Normalize Click option help records to omit metavar suffixes."""

    def get_help_record(self, ctx: click.Context) -> tuple[str, str] | None:
        """
        Return a cleaned help-record tuple for one option.

        Args:
            ctx (click.Context): Active Click context.
        """
        help_record = super().get_help_record(ctx)
        if help_record is not None:
            name, help_text = help_record
            if " " in name and not self.is_flag:
                name = name.rsplit(" ", 1)[0]
            return name, help_text
        return None


class InterfacyListOption(InterfacyClickOption):
    """Accept repeated values for list-like options while preserving None defaults."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        kwargs["nargs"] = 1
        super().__init__(*args, **kwargs)
        self.nargs = -1
        self._interfacy_none_default = kwargs.get("default", None) is None

    def type_cast_value(self, ctx: click.Context, value: object) -> object:
        """
        Cast a list option value while preserving explicit None defaults.

        Args:
            ctx (click.Context): Active Click context.
            value (object): Raw parsed value from Click.
        """
        if value is None and self._interfacy_none_default:
            return None
        return super().type_cast_value(ctx, value)


class InterfacyClickArgument(click.Argument):
    """Carry argument help text and normalize argument help-row names."""

    def __init__(
        self,
        param_decls: Sequence[str],
        required: bool | None = None,
        help: str | None = None,  # noqa: A002 - preserve click-style keyword
        **attrs: object,
    ) -> None:
        self.help = help
        super().__init__(param_decls, required=required, **attrs)

    def get_help_record(self, ctx: click.Context) -> tuple[str, str] | None:
        """
        Return a cleaned help-record tuple for one positional argument.

        Args:
            ctx (click.Context): Active Click context.
        """
        help_record = super().get_help_record(ctx)
        if help_record is not None:
            name, help_text = help_record
            parts = name.split(" ")
            name = " ".join(parts[:-1])
            return name, help_text
        return None


class _HelpMixin:
    interfacy_schema: Command | None = None
    interfacy_parser_schema: ParserSchema | None = None
    interfacy_aliases: tuple[str, ...] = ()
    interfacy_epilog: str | None = None
    interfacy_is_root: bool = False
    params: list[click.Parameter]
    interfacy_param_bindings: dict[str, str]
    interfacy_arg_specs: dict[str, Argument]
    interfacy_suppress_defaults: set[str]
    interfacy_help_position: int | None = None
    interfacy_help_position_explicit: bool = False

    def _resolve_fallback_help_position(self) -> int | None:
        help_position = self.interfacy_help_position
        if not self.interfacy_help_position_explicit or not isinstance(help_position, int):
            return None
        return help_position

    def _render_click_help(self, ctx: click.Context) -> str:
        formatter = InterfacyClickHelpFormatter(
            width=ctx.terminal_width,
            max_width=ctx.max_content_width,
            help_position=self._resolve_fallback_help_position(),
        )
        self.format_help(ctx, formatter)
        return formatter.getvalue().rstrip("\n")

    def _positionals_help_rows(self, ctx: click.Context) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        for param in self.params:
            if not isinstance(param, InterfacyClickArgument):
                continue
            help_record = param.get_help_record(ctx)
            if help_record is None:
                name = param.name or ""
                rows.append((name, param.help or ""))
                continue
            rows.append(help_record)
        return rows

    def format_options(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        if isinstance(formatter, InterfacyClickHelpFormatter):
            positional_rows = self._positionals_help_rows(ctx)
            if positional_rows:
                with formatter.section("Positionals"):
                    formatter.write_dl(positional_rows)
        return super().format_options(ctx, formatter)

    def _augment_help(self, _ctx: click.Context, original_help: str) -> str:
        if "Options:" in original_help:
            description, opts = original_help.split("Options:", 1)
            options = "\n\nOptions:" + opts
        else:
            description = original_help
            options = ""

        positional_lines = []
        for param in self.params:
            if isinstance(param, InterfacyClickArgument):
                positional_name = f"{param.name}".ljust(16)
                arg_help = f"  {positional_name} {param.help or ''}".rstrip()
                positional_lines.append(arg_help)

        extra_help = ""
        if positional_lines:
            extra_help = "Positionals:\n" + "\n".join(positional_lines) + "\n"

        merged = description + extra_help + options
        if self.interfacy_epilog:
            merged = f"{merged.rstrip()}\n\n{self.interfacy_epilog}".rstrip()
        return merged


class InterfacyClickCommand(_HelpMixin, click.Command):
    """Render command help with Interfacy schema-aware formatting."""

    def make_parser(self, ctx: click.Context) -> InterfacyOptionParser:
        """
        Build an option parser bound to this command's parameters.

        Args:
            ctx (click.Context): Active Click context.
        """
        parser = InterfacyOptionParser(ctx)
        for param in self.get_params(ctx):
            param.add_to_parser(parser, ctx)
        return parser

    def get_help(self, ctx: click.Context) -> str:
        """
        Render command help using schema-aware formatting when available.

        Args:
            ctx (click.Context): Active Click context.
        """
        schema = self.interfacy_parser_schema
        if schema is not None and (
            _uses_template_layout(schema.theme) or has_grouped_commands(schema.commands)
        ):
            renderer = SchemaHelpRenderer(schema.theme)
            return renderer.render_parser_help(schema, ctx.command_path)

        schema_command = self.interfacy_schema
        if (
            schema_command is not None
            and schema_command.help_layout is not None
            and (
                _uses_template_layout(schema_command.help_layout)
                or command_has_grouped_subcommands(schema_command)
            )
        ):
            renderer = SchemaHelpRenderer(schema_command.help_layout)
            return renderer.render_command_help(schema_command, ctx.command_path)
        if self._resolve_fallback_help_position() is not None:
            help_text = self._render_click_help(ctx)
            if self.interfacy_epilog:
                return f"{help_text.rstrip()}\n\n{self.interfacy_epilog}".rstrip()
            return help_text
        original_help = super().get_help(ctx)
        return self._augment_help(ctx, original_help)


class InterfacyClickGroup(_HelpMixin, click.Group):
    """Resolve group aliases and render group help with schema metadata."""

    def make_parser(self, ctx: click.Context) -> InterfacyOptionParser:
        """
        Build an option parser bound to this group's parameters.

        Args:
            ctx (click.Context): Active Click context.
        """
        parser = InterfacyOptionParser(ctx)
        for param in self.get_params(ctx):
            param.add_to_parser(parser, ctx)
        return parser

    def get_command(self, ctx: click.Context, name: str) -> click.Command | None:
        """
        Resolve a subcommand by canonical name first, then by Interfacy aliases.

        Args:
            ctx (click.Context): Active Click context.
            name (str): Command token from CLI input.
        """
        command = super().get_command(ctx, name)
        if command is not None:
            return command
        for sub_cmd in self.commands.values():
            aliases = (
                sub_cmd.interfacy_aliases
                if isinstance(sub_cmd, (InterfacyClickCommand, InterfacyClickGroup))
                else ()
            )
            if name in aliases:
                return sub_cmd
        return None

    def list_commands(self, _ctx: click.Context) -> list[str]:
        """Return canonical subcommand names in insertion order."""
        return list(self.commands.keys())

    def get_help(self, ctx: click.Context) -> str:
        """
        Render group help using schema-aware formatting when available.

        Args:
            ctx (click.Context): Active Click context.
        """
        schema = self.interfacy_parser_schema
        if schema is not None and (
            _uses_template_layout(schema.theme) or has_grouped_commands(schema.commands)
        ):
            renderer = SchemaHelpRenderer(schema.theme)
            return renderer.render_parser_help(schema, ctx.command_path)

        schema_command = self.interfacy_schema
        if (
            schema_command is not None
            and schema_command.help_layout is not None
            and (
                _uses_template_layout(schema_command.help_layout)
                or command_has_grouped_subcommands(schema_command)
            )
        ):
            renderer = SchemaHelpRenderer(schema_command.help_layout)
            return renderer.render_command_help(schema_command, ctx.command_path)
        if self._resolve_fallback_help_position() is not None:
            help_text = self._render_click_help(ctx)
            if self.interfacy_epilog:
                return f"{help_text.rstrip()}\n\n{self.interfacy_epilog}".rstrip()
            return help_text
        original_help = super().get_help(ctx)
        return self._augment_help(ctx, original_help)


__all__ = [
    "InterfacyClickArgument",
    "InterfacyClickCommand",
    "InterfacyClickGroup",
    "InterfacyClickOption",
    "InterfacyListOption",
]

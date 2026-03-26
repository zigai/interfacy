from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import click

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
        original_help = super().get_help(ctx)
        return self._augment_help(ctx, original_help)


__all__ = [
    "InterfacyClickArgument",
    "InterfacyClickCommand",
    "InterfacyClickGroup",
    "InterfacyClickOption",
    "InterfacyListOption",
]

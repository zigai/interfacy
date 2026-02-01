from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import click
import click.parser as click_parser

from interfacy.click_backend.parser import InterfacyOptionParser


class InterfacyClickOption(click.Option):
    def get_help_record(self, ctx: click.Context) -> tuple[str, str] | None:
        help_record = super().get_help_record(ctx)
        if help_record is not None:
            name, help_text = help_record
            if " " in name:
                name = name.split(" ")[:-1]
                name = " ".join(name)
            return name, help_text
        return None


class InterfacyListOption(InterfacyClickOption):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["nargs"] = 1
        super().__init__(*args, **kwargs)
        self.nargs = -1
        self._interfacy_none_default = kwargs.get("default", None) is None

    def type_cast_value(self, ctx: click.Context, value: Any) -> Any:
        if value is None and self._interfacy_none_default:
            return None
        return super().type_cast_value(ctx, value)


class InterfacyClickArgument(click.Argument):
    def __init__(
        self,
        param_decls: Sequence[str],
        required: bool | None = None,
        help: str | None = None,
        **attrs: Any,
    ) -> None:
        self.help = help
        super().__init__(param_decls, required=required, **attrs)

    def get_help_record(self, ctx: click.Context) -> tuple[str, str] | None:
        help_record = super().get_help_record(ctx)
        if help_record is not None:
            name, help_text = help_record
            name = name.split(" ")[:-1]
            name = " ".join(name)
            return name, help_text
        return None


class _HelpMixin:
    def _augment_help(self, ctx: click.Context, original_help: str) -> str:
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
        epilog = getattr(self, "_interfacy_epilog", None)
        if epilog:
            merged = f"{merged.rstrip()}\n\n{epilog}".rstrip()
        return merged


class InterfacyClickCommand(_HelpMixin, click.Command):
    def make_parser(self, ctx: click.Context) -> click_parser.OptionParser:
        parser = InterfacyOptionParser(ctx)
        for param in self.get_params(ctx):
            param.add_to_parser(parser, ctx)
        return parser

    def get_help(self, ctx: click.Context) -> str:
        original_help = super().get_help(ctx)
        return self._augment_help(ctx, original_help)


class InterfacyClickGroup(_HelpMixin, click.Group):
    def make_parser(self, ctx: click.Context) -> click_parser.OptionParser:
        parser = InterfacyOptionParser(ctx)
        for param in self.get_params(ctx):
            param.add_to_parser(parser, ctx)
        return parser

    def get_command(self, ctx: click.Context, name: str) -> click.Command | None:
        command = super().get_command(ctx, name)
        if command is not None:
            return command
        for sub_cmd in self.commands.values():
            aliases = getattr(sub_cmd, "_interfacy_aliases", ())
            if name in aliases:
                return sub_cmd
        return None

    def list_commands(self, ctx: click.Context) -> list[str]:
        return list(self.commands.keys())

    def get_help(self, ctx: click.Context) -> str:
        original_help = super().get_help(ctx)
        return self._augment_help(ctx, original_help)


__all__ = [
    "InterfacyClickArgument",
    "InterfacyClickCommand",
    "InterfacyClickGroup",
    "InterfacyClickOption",
    "InterfacyListOption",
]

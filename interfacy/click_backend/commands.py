from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import click

from interfacy.click_backend.parser import InterfacyOptionParser
from interfacy.engine.backend import HelpPipeline
from interfacy.help.content import HelpRenderer
from interfacy.help.layout import HelpLayout
from interfacy.help.presets import StandardLayout
from interfacy.help.renderer import SchemaHelpRenderer
from interfacy.parameters import BooleanMode
from interfacy.schema.schema import (
    Argument,
    ArgumentDefault,
    ArgumentKind,
    BooleanBehavior,
    Command,
    ParserSchema,
    ValueCardinality,
    ValueShape,
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


class InterfacyBooleanOption(InterfacyClickOption):
    """Click option backed by explicit positive and negative flag aliases."""

    def __init__(
        self,
        param_decls: Sequence[str],
        *,
        positive_flags: Sequence[str],
        negative_flags: Sequence[str],
        **kwargs: Any,
    ) -> None:
        self.positive_flags = tuple(positive_flags)
        self.negative_flags = tuple(negative_flags)
        super().__init__(param_decls, **kwargs)
        self.opts = list(self.positive_flags)
        self.secondary_opts = list(self.negative_flags)

    def add_to_parser(self, parser: InterfacyOptionParser, ctx: click.Context) -> None:
        del ctx

        if self.positive_flags:
            parser.add_option(
                obj=self,
                opts=self.positive_flags,
                dest=self.name,
                action="store_const",
                const=True,
            )

        if self.negative_flags:
            parser.add_option(
                obj=self,
                opts=self.negative_flags,
                dest=self.name,
                action="store_const",
                const=False,
            )


class InterfacyListOption(InterfacyClickOption):
    """Accept repeated values for list-like options while preserving None defaults."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["nargs"] = 1
        super().__init__(*args, **kwargs)

        self.nargs = -1
        self._interfacy_none_default = kwargs.get("default", None) is None

    def type_cast_value(self, ctx: click.Context, value: Any) -> Any:
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
        **attrs: Any,
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
            if " " in name:
                name = name.rsplit(" ", 1)[0]

            return name, help_text

        return None


class HelpMixin:
    interfacy_schema: Command | None = None
    interfacy_parser_schema: ParserSchema | None = None
    interfacy_aliases: tuple[str, ...] = ()
    interfacy_is_root: bool = False
    params: list[click.Parameter]
    interfacy_param_bindings: dict[str, str]
    interfacy_arg_specs: dict[str, Argument]
    interfacy_suppress_defaults: set[str]
    interfacy_help_layout: HelpLayout | None = None
    interfacy_help_renderer: HelpRenderer | None = None
    interfacy_help_pipeline: HelpPipeline | None = None
    interfacy_help_command_path: tuple[str, ...] = ()

    def set_help_pipeline(
        self,
        pipeline: HelpPipeline,
        command_path: tuple[str, ...],
    ) -> None:
        """Attach the engine-owned structured help pipeline."""
        self.interfacy_help_pipeline = pipeline
        self.interfacy_help_command_path = command_path

    def get_help(self, ctx: click.Context) -> str:
        """Render all generated and manual help through the structured pipeline."""
        if not isinstance(self, click.Command):
            raise TypeError("HelpMixin must be combined with click.Command")
        if self.interfacy_help_pipeline is not None:
            return self.interfacy_help_pipeline.render(
                self.interfacy_help_command_path,
                ctx.terminal_width,
            )

        layout = self.interfacy_help_layout or StandardLayout()
        help_option = self.get_help_option(ctx)
        help_argument = (
            self._argument_from_click_parameter(help_option) if help_option is not None else None
        )
        renderer = SchemaHelpRenderer(
            layout,
            terminal_width=ctx.terminal_width,
            help_argument=help_argument,
            final_renderer=self.interfacy_help_renderer,
        )
        schema = self.interfacy_parser_schema
        if schema is not None:
            return renderer.render_parser_help(schema, ctx.command_path)

        command = self.interfacy_schema or self._build_implicit_schema_command(ctx)

        return renderer.render_command_help(command, ctx.command_path)

    def _build_implicit_schema_command(self, ctx: click.Context) -> Command:
        if not isinstance(self, click.Command):
            raise TypeError("HelpMixin must be combined with click.Command")

        parameters: list[Argument] = []
        for parameter in self.get_params(ctx):
            if isinstance(parameter, click.Option) and parameter.name == "help":
                continue

            parameters.append(self._argument_from_click_parameter(parameter))

        subcommands: dict[str, Command] | None = None
        if isinstance(self, click.Group):
            subcommands = {}
            for name, child in self.commands.items():
                if isinstance(child, HelpMixin):
                    child_context = click.Context(child, parent=ctx, info_name=name)
                    child_schema = child.interfacy_schema or child._build_implicit_schema_command(
                        child_context
                    )
                else:
                    child_schema = Command(
                        obj=None,
                        canonical_name=name,
                        cli_name=name,
                        aliases=(),
                        raw_description=child.help,
                    )

                subcommands[name] = child_schema

            if not subcommands:
                subcommands = None

        name = self.name or ctx.info_name or "command"

        return Command(
            obj=None,
            canonical_name=name,
            cli_name=name,
            aliases=self.interfacy_aliases,
            raw_description=self.help,
            parameters=parameters,
            subcommands=subcommands,
            raw_epilog=self.epilog,
            command_type="group" if isinstance(self, click.Group) else "function",
            is_leaf=not bool(subcommands),
        )

    @staticmethod
    def _argument_from_click_parameter(parameter: click.Parameter) -> Argument:
        is_option = isinstance(parameter, click.Option)
        is_flag = is_option and parameter.is_flag
        nargs = parameter.nargs
        is_multiple = bool(getattr(parameter, "multiple", False))

        if is_flag:
            value_shape = ValueShape.FLAG
            cardinality = ValueCardinality(0, 0, 0)
        elif is_multiple or nargs == -1:
            value_shape = ValueShape.LIST
            cardinality = ValueCardinality(0, None, 1)
        elif nargs > 1:
            value_shape = ValueShape.TUPLE
            cardinality = ValueCardinality(nargs, nargs, nargs)
        else:
            value_shape = ValueShape.SINGLE
            cardinality = ValueCardinality(1, 1, 1)

        default = getattr(parameter, "default", None)
        boolean_behavior: BooleanBehavior | None = None
        flags = tuple(parameter.opts + parameter.secondary_opts) if is_option else ()

        if is_flag:
            boolean_behavior = BooleanBehavior(
                positive_flags=tuple(parameter.opts),
                negative_flags=tuple(parameter.secondary_opts),
                default=default if isinstance(default, bool) else None,
                mode=BooleanMode.DUAL,
            )

        help_text = (
            parameter.help
            if isinstance(parameter, click.Option)
            else getattr(
                parameter,
                "help",
                None,
            )
        )
        choices = (
            tuple(parameter.type.choices) if isinstance(parameter.type, click.Choice) else None
        )
        metavar = parameter.metavar if isinstance(parameter.metavar, str) else None

        return Argument(
            name=parameter.name or "value",
            display_name=(parameter.name or "value").replace("_", "-"),
            kind=ArgumentKind.OPTION if is_option else ArgumentKind.POSITIONAL,
            value_shape=value_shape,
            flags=flags,
            required=parameter.required,
            cardinality=cardinality,
            argument_default=ArgumentDefault.present(default),
            help=help_text,
            type=None,
            parser=None,
            metavar=metavar,
            boolean_behavior=boolean_behavior,
            choices=choices,
        )


class InterfacyClickCommand(HelpMixin, click.Command):
    """Render command help with Interfacy schema-aware formatting."""

    def __init__(
        self,
        *args: Any,
        help_layout: HelpLayout | None = None,
        help_renderer: HelpRenderer | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.interfacy_help_layout = help_layout
        self.interfacy_help_renderer = help_renderer

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


class InterfacyClickGroup(HelpMixin, click.Group):
    """Resolve group aliases and render group help with schema metadata."""

    def __init__(
        self,
        *args: Any,
        help_layout: HelpLayout | None = None,
        help_renderer: HelpRenderer | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.interfacy_help_layout = help_layout
        self.interfacy_help_renderer = help_renderer

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

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        """
        Resolve a subcommand by canonical name first, then by Interfacy aliases.

        Args:
            ctx (click.Context): Active Click context.
            cmd_name (str): Command token from CLI input.
        """
        command = super().get_command(ctx, cmd_name)
        if command is not None:
            return command

        for sub_cmd in self.commands.values():
            aliases = (
                sub_cmd.interfacy_aliases
                if isinstance(sub_cmd, (InterfacyClickCommand, InterfacyClickGroup))
                else ()
            )
            if cmd_name in aliases:
                return sub_cmd

        return None

    def list_commands(self, ctx: click.Context) -> list[str]:
        """Return canonical subcommand names in insertion order."""
        del ctx

        return list(self.commands.keys())


__all__ = [
    "InterfacyBooleanOption",
    "InterfacyClickArgument",
    "InterfacyClickCommand",
    "InterfacyClickGroup",
    "InterfacyClickOption",
    "InterfacyListOption",
]

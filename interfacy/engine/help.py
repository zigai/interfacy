from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from typing import Any

from interfacy.backends.base import HelpPipeline
from interfacy.common.terminal import get_terminal_width
from interfacy.declarations.settings import BackendName
from interfacy.declarations.sorting import (
    HelpOptionSortRule,
    HelpSubcommandSortRule,
    default_help_option_sort_rules,
    default_help_subcommand_sort_rules,
    resolve_help_option_sort_rules,
    resolve_help_subcommand_sort_rules,
)
from interfacy.engine.plugins import PluginManager
from interfacy.engine.settings import EngineSettings
from interfacy.help import (
    HelpContent,
    HelpContext,
    HelpLayout,
    HelpRenderer,
    StandardLayout,
    default_help_renderer,
)
from interfacy.help.renderer import SchemaHelpRenderer
from interfacy.plugins import HelpHookContext, SchemaDescriptor
from interfacy.schema.model import Command, ParserSchema, find_command

RenderHelp = Callable[[ParserSchema, tuple[str, ...], int | None], str]


class SchemaHelpPipeline(HelpPipeline):
    """Help pipeline that renders one compiled schema through the engine."""

    def __init__(self, render: RenderHelp, schema: ParserSchema) -> None:
        self._render = render
        self._schema = schema

    def render(
        self,
        command_path: tuple[str, ...],
        terminal_width: int | None = None,
    ) -> str:
        return self._render(self._schema, command_path, terminal_width)


def effective_option_sort(
    help_option_sort: Sequence[HelpOptionSortRule] | None,
    layout: HelpLayout,
) -> list[HelpOptionSortRule]:
    """Resolve option help ordering from settings, falling back to layout defaults."""
    value = (
        list(help_option_sort) if help_option_sort is not None else layout.help_option_sort_default
    )
    resolved = resolve_help_option_sort_rules(value, value_name="help_option_sort")

    return list(resolved) if resolved else default_help_option_sort_rules()


def effective_subcommand_sort(
    help_subcommand_sort: Sequence[HelpSubcommandSortRule] | None,
    layout: HelpLayout,
) -> list[HelpSubcommandSortRule]:
    """Resolve subcommand help ordering from settings, falling back to layout defaults."""
    value = (
        list(help_subcommand_sort)
        if help_subcommand_sort is not None
        else layout.help_subcommand_sort_default
    )
    resolved = resolve_help_subcommand_sort_rules(value, value_name="help_subcommand_sort")

    return list(resolved) if resolved else default_help_subcommand_sort_rules()


def configure_help_layout(
    settings: EngineSettings,
    current: HelpLayout,
    reset_fields: frozenset[str] = frozenset(),
) -> HelpLayout:
    """
    Return a help layout configured from ``settings``.

    The layout is copied from ``settings.help_layout`` when set, otherwise from ``current``.
    Fields named in ``reset_fields`` return to their layout defaults. Effective help sort
    rules are installed on the returned layout.
    """
    if "help_layout" in reset_fields:
        layout = StandardLayout()
    elif settings.help_layout is not None:
        layout = deepcopy(settings.help_layout)
    else:
        layout = deepcopy(current)

    if "help_colors" in reset_fields:
        layout.style = type(layout)().style
    elif settings.help_colors is not None:
        layout.style = settings.help_colors

    if settings.help_position is not None:
        layout.help_position = settings.help_position
    elif "help_position" in reset_fields:
        layout.help_position = None

    layout.help_option_sort_rules = effective_option_sort(settings.help_option_sort, layout)
    layout.help_subcommand_sort_rules = effective_subcommand_sort(
        settings.help_subcommand_sort,
        layout,
    )

    return layout


def command_for_path(
    schema: ParserSchema,
    command_path: tuple[str, ...],
) -> Command | None:
    """Return the command addressed by ``command_path``, or ``None`` for the parser root."""
    if not command_path:
        return None

    commands = schema.commands
    current: Command | None = None
    for segment in command_path:
        current = find_command(commands, segment)
        if current is None:
            return None

        commands = current.subcommands or {}

    return current


def render_help(
    schema: ParserSchema,
    command_path: tuple[str, ...],
    terminal_width: int | None,
    *,
    backend: BackendName,
    metadata: Mapping[str, Any],
    plugin_manager: PluginManager,
    help_layout: HelpLayout,
    help_renderer: HelpRenderer | None,
) -> str:
    """Render help for ``command_path`` through help plugins and the configured renderer."""
    program = " ".join(command_path) or "main"
    semantic_path = command_path
    if not semantic_path and len(schema.commands) == 1 and not schema.is_multi_command:
        semantic_path = (next(iter(schema.commands.values())).canonical_name,)
    hook_context = HelpHookContext(
        backend=backend,
        metadata=metadata,
        program=program,
        terminal_width=terminal_width or get_terminal_width(),
        command_path=semantic_path,
        schema=SchemaDescriptor.from_schema(schema),
    )

    def finalize(context: HelpContext, content: HelpContent) -> str:
        transformed = plugin_manager.transform_help(hook_context, content)
        plugin_result = plugin_manager.render_help(hook_context, transformed)
        if plugin_result is not None:
            return plugin_result.text

        if help_renderer is not None:
            return help_renderer(context, transformed)

        return default_help_renderer(context, transformed)

    renderer = SchemaHelpRenderer(
        help_layout,
        terminal_width=hook_context.terminal_width,
        help_flags=schema.help_flags,
        final_renderer=finalize,
    )
    command = command_for_path(schema, command_path)
    if command is None:
        return renderer.render_parser_help(schema, program)

    return renderer.render_command_help(
        command,
        program,
        parser_schema=schema,
    )


__all__ = [
    "RenderHelp",
    "SchemaHelpPipeline",
    "command_for_path",
    "configure_help_layout",
    "effective_option_sort",
    "effective_subcommand_sort",
    "render_help",
]

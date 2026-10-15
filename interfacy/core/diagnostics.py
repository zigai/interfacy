from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from interfacy.common.terminal import get_terminal_width
from interfacy.core.help import command_for_path, render_help
from interfacy.core.plugins import PluginManager
from interfacy.core.recovery import subcommands_at_path
from interfacy.declarations.settings import BackendName
from interfacy.exceptions import ParseDiagnostic, UsageError
from interfacy.help.content import HelpRenderer
from interfacy.help.diagnostics import (
    DiagnosticLayout,
    build_diagnostic_content,
    normalize_diagnostic_text,
)
from interfacy.help.layouts import HelpLayout
from interfacy.help.renderer import SchemaHelpRenderer
from interfacy.plugins import DiagnosticHookContext, SchemaDescriptor
from interfacy.schema.nodes import Command, ParserSchema, find_command


def render_diagnostic(
    failure: UsageError,
    schema: ParserSchema,
    *,
    backend: BackendName,
    metadata: Mapping[str, Any],
    plugin_manager: PluginManager,
    layout: DiagnosticLayout,
    help_layout: HelpLayout,
    help_renderer: HelpRenderer | None,
) -> str:
    diagnostic = failure.diagnostic or ParseDiagnostic(kind="usage", message=str(failure))
    commands = subcommands_at_path(schema, diagnostic.command_path)
    if diagnostic.kind == "unknown_command":
        diagnostic = replace(
            diagnostic,
            choices=tuple(
                name
                for command in commands.values()
                for name in (command.cli_name, *command.aliases)
            ),
        )
    elif diagnostic.kind == "unknown_option":
        diagnostic = replace(diagnostic, choices=option_flags(schema, diagnostic.command_path))

    program = failure.program or Path(sys.argv[0]).name
    width = get_terminal_width()
    context = DiagnosticHookContext(
        backend=backend,
        metadata=metadata,
        program=program,
        terminal_width=width,
        diagnostic=diagnostic,
        schema=SchemaDescriptor.from_schema(schema),
    )

    if diagnostic.kind == "missing_subcommand":
        usage = render_help(
            schema,
            diagnostic.command_path,
            width,
            backend=backend,
            metadata=metadata,
            plugin_manager=plugin_manager,
            help_layout=help_layout,
            help_renderer=help_renderer,
            program=program,
        )
    else:
        usage = SchemaHelpRenderer(
            help_layout, terminal_width=width, help_flags=schema.help_flags
        ).render_usage(schema, program, command=command_for_path(schema, diagnostic.command_path))
    content = build_diagnostic_content(
        diagnostic,
        program=program,
        help_flags=schema.help_flags,
        usage=usage,
    )
    if diagnostic.kind == "unknown_command" and not content.suggestions:
        content = replace(content, choices=tuple(command.cli_name for command in commands.values()))
    transformed = plugin_manager.transform_diagnostic(context, content)
    result = plugin_manager.render_diagnostic(context, transformed)
    text = result.text if result is not None else layout.render(transformed, terminal_width=width)

    return normalize_diagnostic_text(text)


def option_flags(schema: ParserSchema, command_path: tuple[str, ...]) -> tuple[str, ...]:
    flags = [*schema.help_flags]
    flags.extend(flag for action in schema.executable_flags for flag in action.flags)
    chain: list[Command] = []
    commands = schema.commands
    if len(commands) == 1 and not schema.is_multi_command:
        command = next(iter(commands.values()))
        if command.command_type != "group":
            chain.append(command)
            commands = command.subcommands or {}

    for segment in command_path:
        command = find_command(commands, segment)
        if command is None:
            break

        chain.append(command)
        commands = command.subcommands or {}

    for command in chain:
        for argument in (*command.initializer, *command.arguments):
            flags.extend(argument.flags)
            if argument.boolean_behavior is not None:
                flags.extend(argument.boolean_behavior.positive_flags)
                flags.extend(argument.boolean_behavior.negative_flags)

        flags.extend(flag for action in command.executable_flags for flag in action.flags)

    return tuple(dict.fromkeys(flags))


__all__ = ["option_flags", "render_diagnostic"]

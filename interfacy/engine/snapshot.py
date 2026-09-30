from __future__ import annotations

from dataclasses import dataclass

from interfacy.engine.compiler import CompiledParser
from interfacy.engine.pipes import PipeState, PipeStateSnapshot
from interfacy.engine.plugins import PluginManager
from interfacy.engine.registry import CommandRegistry, NameRegistrySnapshot
from interfacy.naming import FlagStrategy
from interfacy.plugins import InterfacyPlugin
from interfacy.schema.model import Command, ParserSchema


@dataclass(frozen=True, slots=True)
class EngineSnapshot:
    """Mutable engine state captured before registration or inline invocation."""

    registry_commands: dict[str, Command]
    registry_names: NameRegistrySnapshot
    registry_generation: int
    plugins: list[InterfacyPlugin]
    plugin_names: set[str]
    plugin_generation: int
    pipes: PipeStateSnapshot
    last_schema: ParserSchema | None
    compiled: CompiledParser | None
    command_translations: dict[str, str]
    argument_translations: dict[str, str]

    @classmethod
    def capture(
        cls,
        *,
        registry: CommandRegistry,
        plugin_manager: PluginManager,
        pipes: PipeState,
        flag_strategy: FlagStrategy,
        last_schema: ParserSchema | None,
        compiled: CompiledParser | None,
    ) -> EngineSnapshot:
        """Capture the current state of the given engine components."""
        commands, names, registry_generation = registry.snapshot()
        plugins, plugin_names, plugin_generation = plugin_manager.snapshot()

        return cls(
            registry_commands=commands,
            registry_names=names,
            registry_generation=registry_generation,
            plugins=plugins,
            plugin_names=plugin_names,
            plugin_generation=plugin_generation,
            pipes=pipes.snapshot(),
            last_schema=last_schema,
            compiled=compiled,
            command_translations=dict(flag_strategy.command_translator.translations),
            argument_translations=dict(flag_strategy.argument_translator.translations),
        )

    def restore_components(
        self,
        *,
        registry: CommandRegistry,
        plugin_manager: PluginManager,
        pipes: PipeState,
        flag_strategy: FlagStrategy,
    ) -> None:
        """Restore the captured registry, plugin, pipe, and name-translation state in place."""
        registry.restore(
            self.registry_commands,
            self.registry_names,
            self.registry_generation,
        )
        plugin_manager.restore(
            self.plugins,
            self.plugin_names,
            self.plugin_generation,
        )
        pipes.restore(self.pipes)
        flag_strategy.command_translator.translations.clear()
        flag_strategy.command_translator.translations.update(self.command_translations)
        flag_strategy.argument_translator.translations.clear()
        flag_strategy.argument_translator.translations.update(self.argument_translations)


__all__ = ["EngineSnapshot"]

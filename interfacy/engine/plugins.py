from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from functools import partial
from typing import Any

from interfacy.exceptions import ConfigurationError, DuplicatePluginError
from interfacy.help.content import HelpContent, HelpResult
from interfacy.plugins import (
    AbortRecovery,
    AfterParseContext,
    BackendPlugin,
    BackendPluginContext,
    BeforeParseContext,
    ConfigureContext,
    ExecuteContext,
    HelpHookContext,
    InterfacyPlugin,
    ParseFailure,
    ParseFailureContext,
    ProvideArgumentValues,
    RecoveryAction,
    SchemaTransformContext,
)
from interfacy.schema.schema import ParserSchema


class PluginManager:
    def __init__(self) -> None:
        self.plugins: list[InterfacyPlugin] = []
        self.names: set[str] = set()
        self._generation = 0

    @property
    def generation(self) -> int:
        return self._generation

    def validate_additions(
        self,
        plugins: Sequence[InterfacyPlugin],
        backend: str,
    ) -> tuple[InterfacyPlugin, ...]:
        additions = tuple(plugins)
        names = set(self.names)
        for plugin in additions:
            if not isinstance(plugin, InterfacyPlugin):
                raise ConfigurationError("plugins must contain InterfacyPlugin instances")
            name = plugin.plugin_name
            if name in names:
                raise DuplicatePluginError(name)
            if isinstance(plugin, BackendPlugin) and plugin.backend != backend:
                raise ConfigurationError(
                    f"Plugin '{name}' requires backend '{plugin.backend}', got '{backend}'"
                )
            names.add(name)
        return additions

    def commit_additions(self, plugins: Sequence[InterfacyPlugin]) -> None:
        additions = tuple(plugins)
        self.plugins.extend(additions)
        self.names.update(plugin.plugin_name for plugin in additions)
        self._generation += len(additions)

    def add(
        self,
        plugin: InterfacyPlugin,
        context: ConfigureContext,
        backend_context: BackendPluginContext,
    ) -> InterfacyPlugin:
        self.validate_additions((plugin,), backend_context.backend)
        plugin.configure(context)
        if isinstance(plugin, BackendPlugin):
            plugin.configure_backend(backend_context)
        self.commit_additions((plugin,))
        return plugin

    def attach_backend_plugins(self, context: BackendPluginContext) -> None:
        for plugin in self.plugins:
            if isinstance(plugin, BackendPlugin):
                plugin.configure_backend(context)

    def before_parse(
        self,
        context_factory: Callable[[tuple[str, ...]], BeforeParseContext],
        args: Sequence[str],
    ) -> tuple[str, ...]:
        current = tuple(args)
        for plugin in self.plugins:
            result = plugin.before_parse(context_factory(current), current)
            current = self._validate_args(plugin.plugin_name, "before_parse", result)
        return current

    def after_parse(
        self,
        context_factory: Callable[[Mapping[str, Any]], AfterParseContext],
        namespace: Mapping[str, Any],
    ) -> dict[str, Any]:
        current = dict(namespace)
        for plugin in self.plugins:
            result = plugin.after_parse(context_factory(current), current)
            current = self._validate_namespace(plugin.plugin_name, "after_parse", result)
        return current

    def execute(
        self,
        context: ExecuteContext,
        call_next: Callable[[], Any],
    ) -> Any:
        wrapped = call_next
        for plugin in reversed(self.plugins):
            wrapped = partial(plugin.wrap_execute, context, wrapped)
        return wrapped()

    def transform_schema(
        self,
        context: SchemaTransformContext,
        schema: ParserSchema,
    ) -> ParserSchema:
        current = schema
        for plugin in self.plugins:
            result = plugin.transform_schema(context, current)
            if not isinstance(result, ParserSchema):
                self._invalid_result(plugin.plugin_name, "transform_schema", "ParserSchema")
            current = result
        return current

    def transform_help(
        self,
        context: HelpHookContext,
        content: HelpContent,
    ) -> HelpContent:
        current = content
        for plugin in self.plugins:
            result = plugin.transform_help(context, current)
            if not isinstance(result, HelpContent):
                self._invalid_result(plugin.plugin_name, "transform_help", "HelpContent")
            current = result
        return current

    def render_help(
        self,
        context: HelpHookContext,
        content: HelpContent,
    ) -> HelpResult | None:
        for plugin in self.plugins:
            result = plugin.render_help(context, content)
            if result is None:
                continue
            if not isinstance(result, HelpResult):
                self._invalid_result(plugin.plugin_name, "render_help", "HelpResult | None")
            return result
        return None

    def recover(
        self,
        context: ParseFailureContext,
        failure: ParseFailure,
    ) -> RecoveryAction | None:
        for plugin in self.plugins:
            action = plugin.recover_parse_failure(context, failure)
            if action is None:
                continue
            if not isinstance(action, (ProvideArgumentValues, AbortRecovery)):
                self._invalid_result(
                    plugin.plugin_name,
                    "recover_parse_failure",
                    "ProvideArgumentValues | AbortRecovery | None",
                )
            return action
        return None

    def snapshot(self) -> tuple[list[InterfacyPlugin], set[str], int]:
        return list(self.plugins), set(self.names), self._generation

    def restore(
        self,
        plugins: Sequence[InterfacyPlugin],
        names: set[str],
        generation: int | None = None,
    ) -> None:
        self.plugins = list(plugins)
        self.names = set(names)
        self._generation = self._generation + 1 if generation is None else generation

    @staticmethod
    def _validate_args(
        plugin_name: str,
        hook: str,
        value: Sequence[str],
    ) -> tuple[str, ...]:
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            PluginManager._invalid_result(plugin_name, hook, "Sequence[str]")
        args = tuple(value)
        if not all(isinstance(item, str) for item in args):
            PluginManager._invalid_result(plugin_name, hook, "Sequence[str]")
        return args

    @staticmethod
    def _validate_namespace(
        plugin_name: str,
        hook: str,
        value: Mapping[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            PluginManager._invalid_result(plugin_name, hook, "Mapping[str, object]")
        if not all(isinstance(key, str) for key in value):
            PluginManager._invalid_result(plugin_name, hook, "Mapping[str, object]")
        return dict(value)

    @staticmethod
    def _invalid_result(plugin_name: str, hook: str, expected: str) -> None:
        raise ConfigurationError(f"Plugin '{plugin_name}' hook '{hook}' must return {expected}")


__all__ = ["PluginManager"]

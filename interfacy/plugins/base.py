from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, ClassVar

from interfacy.declarations.settings import BackendName
from interfacy.help.content import HelpContent, HelpResult
from interfacy.plugins.contexts import (
    AfterParseContext,
    BackendPluginContext,
    BeforeParseContext,
    ConfigureContext,
    ExecuteContext,
    HelpHookContext,
    ParseFailureContext,
    SchemaTransformContext,
)
from interfacy.plugins.recovery import ParseFailure, RecoveryAction
from interfacy.schema.model import ParserSchema


class InterfacyPlugin:
    """Base class for portable, backend-neutral Interfacy plugins."""

    name: str | None = None

    def configure(self, context: ConfigureContext) -> None:
        """Configure portable capabilities immediately after registration."""
        del context

    def before_parse(
        self,
        context: BeforeParseContext,
        args: tuple[str, ...],
    ) -> Sequence[str]:
        """Transform raw CLI arguments before backend parsing."""
        del context

        return args

    def after_parse(
        self,
        context: AfterParseContext,
        namespace: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Transform the parsed namespace before it is returned."""
        del context

        return namespace

    def transform_schema(
        self,
        context: SchemaTransformContext,
        schema: ParserSchema,
    ) -> ParserSchema:
        """Transform the explicit mutable schema payload."""
        del context

        return schema

    def transform_help(
        self,
        context: HelpHookContext,
        content: HelpContent,
    ) -> HelpContent:
        """Transform structured help content before final rendering."""
        del context

        return content

    def render_help(
        self,
        context: HelpHookContext,
        content: HelpContent,
    ) -> HelpResult | None:
        """Optionally provide final rendered help text."""
        del context, content

        return None

    def wrap_execute(
        self,
        context: ExecuteContext,
        call_next: Callable[[], Any],
    ) -> Any:
        """Wrap command execution."""
        del context

        return call_next()

    def recover_parse_failure(
        self,
        context: ParseFailureContext,
        failure: ParseFailure,
    ) -> RecoveryAction | None:
        """Optionally recover from a structured parse failure."""
        del context, failure

        return None

    @property
    def plugin_name(self) -> str:
        """Return the unique parser-local name used for plugin registration."""
        explicit_name = self.name
        if explicit_name:
            return explicit_name

        return type(self).__name__


class BackendPlugin(InterfacyPlugin):
    """Plugin opting into backend-specific, compatibility-limited adapter access."""

    backend: ClassVar[BackendName]

    def configure_backend(self, context: BackendPluginContext) -> None:
        """Configure against the selected backend's explicit native-access context."""
        del context


__all__ = ["BackendPlugin", "InterfacyPlugin"]

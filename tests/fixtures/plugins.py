"""Reusable plugin doubles for backend contract tests."""

from operator import setitem

import pytest

from interfacy.plugins import (
    BackendPlugin,
    BackendPluginContext,
    ConfigureContext,
    InterfacyPlugin,
)


class MarkerPlugin(InterfacyPlugin):
    name = "marker"

    def __init__(self) -> None:
        self.configured = False

    def configure(self, context) -> None:
        del context
        self.configured = True


class ImmutableContextPlugin(InterfacyPlugin):
    name = "immutable_context"

    def configure(self, context: ConfigureContext) -> None:
        with pytest.raises(TypeError):
            setitem(context.metadata, "mutated", "yes")
        nested = context.metadata["nested"]
        with pytest.raises(TypeError):
            setitem(nested, "mutated", "yes")
        with pytest.raises(TypeError):
            setitem(nested["values"], 0, "changed")


class ArgparseAccessPlugin(BackendPlugin):
    name = "argparse_access"
    backend = "argparse"

    def __init__(self) -> None:
        self.adapter_name: str | None = None

    def configure_backend(self, context: BackendPluginContext) -> None:
        self.adapter_name = type(context.adapter).__name__


class SchemaMetadataPlugin(InterfacyPlugin):
    name = "schema_metadata"

    def transform_schema(self, context, schema):
        assert context.metadata.get("environment") is None
        schema.metadata["transformed"] = True
        command = next(iter(schema.commands.values()))
        command.raw_description = "Plugin description"

        return schema

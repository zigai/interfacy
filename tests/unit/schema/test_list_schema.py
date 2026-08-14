from objinspect import Function

from interfacy.help.renderer import SchemaHelpRenderer
from interfacy.schema.builder import ParserSchemaBuilder
from interfacy.schema.schema import ValueShape
from tests.fixtures.commands import fn_list_int_optional, fn_list_str, fn_list_str_optional
from tests.unit.schema.conftest import SchemaSource


def test_list_positional_schema(schema_source: SchemaSource):
    """Verify required list positional has unbounded required cardinality."""
    func = Function(fn_list_str)
    schema_source.register_command(func, canonical_name="fn-list-str")
    builder = ParserSchemaBuilder(schema_source.schema_context())

    schema = builder.build()
    cmd = schema.commands["fn-list-str"]
    arg = next(i for i in cmd.parameters if i.name == "items")
    assert arg.value_shape is ValueShape.LIST
    assert arg.cardinality.minimum_values == 1
    assert arg.cardinality.maximum_values is None


def test_list_optional_union_schema(schema_source: SchemaSource):
    """Verify list|None has value_shape=LIST, nargs='*'."""
    func = Function(fn_list_str_optional)
    schema_source.register_command(func, canonical_name="fn-list-str-optional")
    builder = ParserSchemaBuilder(schema_source.schema_context())

    schema = builder.build()
    cmd = schema.commands["fn-list-str-optional"]
    arg = next(i for i in cmd.parameters if i.name == "items")
    assert arg.value_shape is ValueShape.LIST
    assert arg.cardinality.minimum_values == 0
    assert arg.cardinality.maximum_values is None


def test_list_default_not_shared(schema_source: SchemaSource):
    """Verify that default None does not create shared mutable state."""
    func = Function(fn_list_int_optional)
    param = func.params[0]
    builder = ParserSchemaBuilder(schema_source.schema_context())
    taken = [*schema_source.RESERVED_FLAGS]

    arg1 = builder._argument_from_parameter(param, taken[:])[0]
    arg2 = builder._argument_from_parameter(param, taken[:])[0]

    assert (
        arg1.argument_default.value is not arg2.argument_default.value
        or arg1.argument_default.value is None
    )


def test_required_list_positional_usage_is_not_rendered_as_optional(
    schema_source: SchemaSource,
):
    """Required list positionals should not render with optional brackets in usage."""
    func = Function(fn_list_str)
    schema_source.register_command(func, canonical_name="fn-list-str")
    builder = ParserSchemaBuilder(schema_source.schema_context())

    schema = builder.build()
    cmd = schema.commands["fn-list-str"]
    help_text = SchemaHelpRenderer(schema_source.help_layout).render_command_help(cmd, "prog")

    assert "[ITEMS ...]" not in help_text

from objinspect import Function

from interfacy.schema.builder import ParserSchemaBuilder
from interfacy.schema.schema import ValueShape
from tests.conftest import fn_list_int_optional, fn_list_str, fn_list_str_optional
from tests.schema.conftest import FakeParser


def test_list_positional_schema(builder_parser: FakeParser):
    """Verify list positional has value_shape=LIST, nargs='*'."""
    func = Function(fn_list_str)
    builder_parser.register_command(func, canonical_name="fn-list-str")
    builder = ParserSchemaBuilder(builder_parser)

    schema = builder.build()
    cmd = schema.commands["fn-list-str"]
    arg = next(i for i in cmd.parameters if i.name == "items")
    assert arg.value_shape is ValueShape.LIST
    assert arg.nargs == "*"


def test_list_optional_union_schema(builder_parser: FakeParser):
    """Verify list|None has value_shape=LIST, nargs='*'."""
    func = Function(fn_list_str_optional)
    builder_parser.register_command(func, canonical_name="fn-list-str-optional")
    builder = ParserSchemaBuilder(builder_parser)

    schema = builder.build()
    cmd = schema.commands["fn-list-str-optional"]
    arg = next(i for i in cmd.parameters if i.name == "items")
    assert arg.value_shape is ValueShape.LIST
    assert arg.nargs == "*"


def test_list_default_not_shared(builder_parser: FakeParser):
    """Verify that default None does not create shared mutable state."""
    func = Function(fn_list_int_optional)
    param = func.params[0]
    builder = ParserSchemaBuilder(builder_parser)
    taken = [*builder_parser.RESERVED_FLAGS]

    arg1 = builder._argument_from_parameter(param, taken[:])[0]
    arg2 = builder._argument_from_parameter(param, taken[:])[0]

    # Either None (preserved) or different [] instances
    assert arg1.default is not arg2.default or arg1.default is None

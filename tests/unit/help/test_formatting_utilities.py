from interfacy.help.formatting import format_default_for_help
from interfacy.schema.typing import extract_optional_union_list, simplified_type_name


def test_simplified_type_name_keeps_generic_shape_for_qualified_names() -> None:
    assert simplified_type_name("dict[builtins.str, mypkg.Foo]") == "dict[str, Foo]"
    assert simplified_type_name("mypkg.Outer[mypkg.Inner]") == "Outer[Inner]"
    assert simplified_type_name("typing.Union[mypkg.Foo, None]") == "Foo?"


def test_simplified_type_name_preserves_quoted_literal_values() -> None:
    assert simplified_type_name("typing.Literal['a.b', mypkg.Foo]") == "Literal['a.b', Foo]"


def test_extract_optional_union_list_requires_exactly_list_or_none_union() -> None:
    assert extract_optional_union_list(list[int] | None) == (list[int], int)
    assert extract_optional_union_list(list[int] | str | None) is None


def test_format_default_for_help_renders_empty_string_with_quotes() -> None:
    assert format_default_for_help("") == '""'


def test_format_default_for_help_keeps_non_empty_strings_unquoted() -> None:
    assert format_default_for_help("sqlite.db") == "sqlite.db"

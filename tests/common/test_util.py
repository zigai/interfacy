from interfacy import util


def test_simplified_type_name_keeps_generic_shape_for_qualified_names() -> None:
    assert util.simplified_type_name("dict[builtins.str, mypkg.Foo]") == "dict[str, Foo]"
    assert util.simplified_type_name("mypkg.Outer[mypkg.Inner]") == "Outer[Inner]"
    assert util.simplified_type_name("typing.Union[mypkg.Foo, None]") == "Foo?"


def test_simplified_type_name_preserves_quoted_literal_values() -> None:
    assert util.simplified_type_name("typing.Literal['a.b', mypkg.Foo]") == "Literal['a.b', Foo]"


def test_extract_optional_union_list_requires_exactly_list_or_none_union() -> None:
    assert util.extract_optional_union_list(list[int] | None) == (list[int], int)
    assert util.extract_optional_union_list(list[int] | str | None) is None

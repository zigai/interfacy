from interfacy.help.formatting import format_default_for_help
from interfacy.introspection.annotations import extract_optional_union_list


def test_extract_optional_union_list_requires_exactly_list_or_none_union() -> None:
    assert extract_optional_union_list(list[int] | None) == (list[int], int)
    assert extract_optional_union_list(list[int] | str | None) is None


def test_format_default_for_help_renders_empty_string_with_quotes() -> None:
    assert format_default_for_help("") == '""'


def test_format_default_for_help_keeps_non_empty_strings_unquoted() -> None:
    assert format_default_for_help("sqlite.db") == "sqlite.db"

from interfacy.help.formatting import format_default_for_help


def test_format_default_for_help_renders_empty_string_with_quotes() -> None:
    assert format_default_for_help("") == '""'


def test_format_default_for_help_keeps_non_empty_strings_unquoted() -> None:
    assert format_default_for_help("sqlite.db") == "sqlite.db"

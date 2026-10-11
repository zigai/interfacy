import pytest

from interfacy.help.formatting import format_default_for_help


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("", '""', id="empty"),
        pytest.param("sqlite.db", "sqlite.db", id="non-empty"),
    ],
)
def test_format_default_for_help_quotes_only_empty_strings(value: str, expected: str) -> None:
    assert format_default_for_help(value) == expected

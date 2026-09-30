from interfacy import Interfacy
from interfacy.naming import DefaultFlagStrategy
from tests.fixtures.commands import fn_list_str


def test_required_list_positional_usage_is_not_rendered_as_optional() -> None:
    """Required list positionals should not render with optional brackets in usage."""
    parser = Interfacy(flag_strategy=DefaultFlagStrategy(style="required_positional"))
    parser.add_command(fn_list_str)

    help_text = parser.build_parser().format_help()

    assert "ITEMS" in help_text
    assert "[ITEMS ...]" not in help_text

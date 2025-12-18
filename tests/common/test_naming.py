import pytest
from objinspect import Function
from stdl.st import kebab_case

from interfacy.exceptions import DuplicateCommandError
from interfacy.naming.abbreviations import DefaultAbbreviationGenerator, NoAbbreviations
from interfacy.naming.command_naming import CommandNameRegistry
from interfacy.naming.flag_strategy import DefaultFlagStrategy
from interfacy.naming.name_mapping import NameMapping, reverse_translations


def test_command_name_registry_collisions():
    """Verify that CommandNameRegistry correctly detects various naming collisions."""
    registry = CommandNameRegistry(NameMapping(kebab_case))

    registry.register(default_name="list_files")

    with pytest.raises(DuplicateCommandError):  # Duplicate canonical name
        registry.register(default_name="list_files")

    with pytest.raises(DuplicateCommandError):  # Explicit name collision with existing canonical
        registry.register(default_name="other", explicit_name="list-files")

    with pytest.raises(DuplicateCommandError):  # Alias collision with existing canonical
        registry.register(default_name="other", aliases=["list-files"])

    registry.register(default_name="show_hidden", aliases=["sh"])

    with pytest.raises(DuplicateCommandError):  # Canonical name collision with existing alias
        registry.register(default_name="sh")

    with pytest.raises(DuplicateCommandError):  # Alias collision with existing alias
        registry.register(default_name="sort_by", aliases=["sh"])

    with pytest.raises(DuplicateCommandError):  # Alias same as its own canonical
        registry.register(default_name="filter", aliases=["filter"])

    with pytest.raises(DuplicateCommandError):  # Duplicate alias in same registration
        registry.register(default_name="format", aliases=["f", "f"])


def test_command_name_registry_lookups():
    """Verify canonical name lookups for primary names and aliases."""
    registry = CommandNameRegistry(NameMapping(kebab_case))
    registry.register(default_name="output_format", aliases=["of", "fmt"])

    assert registry.canonical_for("output-format") == "output-format"
    assert registry.canonical_for("of") == "output-format"
    assert registry.canonical_for("fmt") == "output-format"
    assert registry.canonical_for("unknown") is None


def test_abbreviation_generator_logic():
    """Verify DefaultAbbreviationGenerator fallback logic and conflict handling."""
    gen = DefaultAbbreviationGenerator()
    taken: list[str] = []

    # First char: "verbose" -> "v"
    assert gen.generate("verbose", taken) == "v"
    assert "v" in taken

    # Conflict on first char -> initials: "version_check" -> "vc"
    assert gen.generate("version_check", taken) == "vc"
    assert "vc" in taken

    # Conflict on first char and initials -> first 2 chars: "validate" -> "va"
    taken = ["v", "vc"]
    assert gen.generate("validate", taken) == "va"
    assert "va" in taken

    # Exhaustion: all fallbacks taken
    taken = ["v", "vc", "ve"]
    assert gen.generate("version_check", taken) is None


def test_name_mapping_roundtrip():
    """Verify that NameMapping correctly handles forward and reverse translations."""
    mapping = NameMapping(kebab_case)

    assert mapping.translate("output_path") == "output-path"
    assert mapping.reverse("output-path") == "output_path"
    assert mapping.reverse("unknown") == "unknown"


def test_reverse_translations_util():
    """Verify that reverse_translations utility correctly maps dictionaries."""
    mapping = NameMapping(kebab_case)
    mapping.translate("user_id")
    mapping.translate("is_active")

    cli_args = {"user-id": 123, "is-active": True, "extra": "data"}
    reversed_args = reverse_translations(cli_args, mapping)

    assert reversed_args == {"user_id": 123, "is_active": True, "extra": "data"}


def test_flag_strategy_boolean_inversion_short_flags():
    """Verify DefaultFlagStrategy generates correct flags for inverted booleans."""
    strategy = DefaultFlagStrategy(style="keyword_only")
    gen = DefaultAbbreviationGenerator()
    taken: list[str] = []

    def fn_verbose(verbose: bool = True):
        pass

    param = Function(fn_verbose).params[0]
    flags = strategy.get_arg_flags("verbose", param, taken, gen)

    # Boolean with default=True generates --verbose with short -nv (no-verbose)
    assert "--verbose" in flags
    assert "-nv" in flags


def test_flag_strategy_positional_logic():
    """Verify DefaultFlagStrategy distinguishes positional vs optional arguments."""
    strategy = DefaultFlagStrategy(style="required_positional")
    gen = NoAbbreviations()
    taken: list[str] = []

    def fn_path(path: str):
        pass

    param_req = Function(fn_path).params[0]
    assert strategy.get_arg_flags("path", param_req, taken, gen) == ("path",)

    def fn_timeout(timeout: int = 30):
        pass

    param_opt = Function(fn_timeout).params[0]
    assert strategy.get_arg_flags("timeout", param_opt, taken, gen) == ("--timeout",)

from __future__ import annotations

import pytest

from interfacy import Param, params
from interfacy.core import InterfacyParser
from interfacy.exceptions import ConfigurationError


@params(config=Param(kind="positional", metavar="CONFIG"))
def validate(config: str | None = None) -> str | None:
    """Validate configuration."""
    return config


@params(values=Param(kind="positional"))
def collect_values(values: list[int] | None = None) -> list[int]:
    """Collect optional integer values."""
    return values or []


@params(values=Param(kind="positional"))
def defaulted_values(values: list[int] = [5]) -> list[int]:  # noqa: B006 - intentional for tests
    """Return defaulted optional integer values."""
    return values


@params(profile=Param(kind="positional"))
def defaulted_profile(profile: str = "default") -> str:
    """Return a defaulted optional positional value."""
    return profile


@params(value=Param(kind="option"))
def required_option(value: str) -> str:
    """Require a value through an option."""
    return value


def lint() -> str:
    """Placeholder command used to keep validate as an explicit subcommand."""
    return "lint"


@params(config=Param(kind="positional"))
class ToolWithOptionalInitializerPositional:
    """Tool with an unsafe optional initializer positional."""

    def __init__(self, config: str | None = None) -> None:
        self.config = config

    def run(self) -> str | None:
        """Run the tool."""
        return self.config


@params(config=Param(kind="positional"))
def optional_before_required(
    config: str | None = None,
    *,
    target: str,
) -> tuple[str | None, str]:
    """Place an optional positional before a required positional."""
    return config, target


def test_param_kind_rejects_unknown_values() -> None:
    with pytest.raises(ConfigurationError, match=r"Param\.kind"):
        Param(kind="argument")  # type: ignore[arg-type]


def test_positional_param_kind_rejects_flag_overrides() -> None:
    with pytest.raises(ConfigurationError, match="cannot be combined"):
        Param(kind="positional", long="config")


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_optional_scalar_positional_can_be_omitted_or_provided(
    parser: InterfacyParser,
) -> None:
    parser.add_command(validate)

    assert parser.run(args=[]) is None
    assert parser.run(args=["pyproject.toml"]) == "pyproject.toml"


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_validate_config_regression_uses_optional_config_positional(
    parser: InterfacyParser,
) -> None:
    parser.add_command(lint)
    parser.add_command(validate)

    assert parser.run(args=["validate"]) is None
    assert parser.run(args=["validate", "custom.toml"]) == "custom.toml"


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_optional_list_positional_accepts_zero_or_more_values(
    parser: InterfacyParser,
) -> None:
    parser.add_command(collect_values)

    assert parser.run(args=[]) == []
    assert parser.run(args=["1", "2"]) == [1, 2]


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_defaulted_scalar_positional_preserves_default(parser: InterfacyParser) -> None:
    parser.add_command(defaulted_profile)

    assert parser.run(args=[]) == "default"
    assert parser.run(args=["custom"]) == "custom"


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_defaulted_list_positional_preserves_default(parser: InterfacyParser) -> None:
    parser.add_command(defaulted_values)

    assert parser.run(args=[]) == [5]
    assert parser.run(args=["1", "2"]) == [1, 2]


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_param_kind_option_forces_required_parameter_to_option(
    parser: InterfacyParser,
) -> None:
    parser.add_command(required_option)

    assert parser.run(args=["--value", "provided"]) == "provided"


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_optional_initializer_positionals_are_rejected_for_class_subcommands(
    parser: InterfacyParser,
) -> None:
    parser.add_command(ToolWithOptionalInitializerPositional)

    with pytest.raises(ConfigurationError, match="Optional initializer positional"):
        parser.build_parser_schema()


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_optional_positionals_cannot_precede_required_positionals(
    parser: InterfacyParser,
) -> None:
    parser.add_command(optional_before_required)

    with pytest.raises(ConfigurationError, match="cannot appear before positional parameter"):
        parser.build_parser_schema()

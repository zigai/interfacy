import inspect
from dataclasses import fields

import pytest

from interfacy import CommandGroup, Interfacy
from interfacy.cli.config import InterfacyConfig
from interfacy.declarations.options import COMMAND_OPTION_NAMES, OVERRIDE_NAMES
from interfacy.engine.settings import SETTING_NAMES, UPDATE_POLICIES, EngineSettings

# Constructor parameters that configure the facade itself rather than the engine settings.
FACADE_ONLY_PARAMETERS = frozenset({"backend", "sys_exit_enabled"})
# Config-file keys consumed while resolving other settings.
CONFIG_ONLY_FIELDS = frozenset({"backend", "flag_style", "translation_mode"})
# Registration parameters that identify the command rather than configure it.
REGISTRATION_PARAMETERS = frozenset(
    {"command", "group", "name", "description", "aliases", "pipe_targets"}
)


def parameters(function: object) -> dict[str, inspect.Parameter]:
    return {
        name: parameter
        for name, parameter in inspect.signature(function).parameters.items()  # type: ignore[arg-type]
        if name != "self"
    }


def test_constructor_parameters_match_engine_settings() -> None:
    constructor = parameters(Interfacy.__init__)

    assert set(constructor) - FACADE_ONLY_PARAMETERS == SETTING_NAMES


def test_constructor_defaults_match_engine_settings() -> None:
    constructor = parameters(Interfacy.__init__)

    for setting in fields(EngineSettings):
        assert constructor[setting.name].default == setting.default, setting.name


def test_apply_setup_parameters_match_update_policies() -> None:
    assert set(parameters(Interfacy.apply_setup)) == set(UPDATE_POLICIES)


def test_config_fields_name_engine_settings() -> None:
    config_fields = {config_field.name for config_field in fields(InterfacyConfig)}

    assert config_fields - CONFIG_ONLY_FIELDS <= SETTING_NAMES


@pytest.mark.parametrize(
    "register",
    [Interfacy.add_command, Interfacy.command, Interfacy.add_group, CommandGroup.add_command],
)
def test_registration_parameters_match_command_options(register: object) -> None:
    assert set(parameters(register)) - REGISTRATION_PARAMETERS == set(COMMAND_OPTION_NAMES)


def test_command_overrides_name_engine_settings() -> None:
    assert set(OVERRIDE_NAMES) <= SETTING_NAMES

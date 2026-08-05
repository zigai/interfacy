from __future__ import annotations

from typing import Literal

import pytest

from interfacy import BooleanMode, Interfacy, Param, params
from interfacy.exceptions import ConfigurationError


def test_param_rejects_unknown_boolean_mode() -> None:
    with pytest.raises(ConfigurationError, match=r"Param\.boolean_mode must be one of"):
        Param(boolean_mode="sometimes")


def test_positional_param_rejects_boolean_settings() -> None:
    with pytest.raises(ConfigurationError, match="cannot be combined with flag or boolean"):
        Param(kind="positional", boolean_mode="dual")


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_dual_mode_exposes_both_values_for_false_default(
    backend: Literal["argparse", "click"],
) -> None:
    def command(*, color: bool = False) -> bool:
        return color

    parser = Interfacy(backend=backend, sys_exit_enabled=False)
    parser.add_command(
        command,
        parameter_settings={"color": Param(boolean_mode="dual")},
    )

    assert parser.run(args=[]) is False
    assert parser.run(args=["--color"]) is True
    assert parser.run(args=["--no-color"]) is False


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_auto_mode_rejects_forms_that_only_restate_defaults(
    backend: Literal["argparse", "click"],
) -> None:
    def command(*, cache: bool = True, verbose: bool = False) -> tuple[bool, bool]:
        return cache, verbose

    parser = Interfacy(backend=backend, sys_exit_enabled=False)
    parser.add_command(command)

    positive_default_result = parser.run(args=["--cache"])
    negative_default_result = parser.run(args=["--no-verbose"])

    assert isinstance(positive_default_result, SystemExit)
    assert positive_default_result.code == 2
    assert isinstance(negative_default_result, SystemExit)
    assert negative_default_result.code == 2


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_custom_negative_flags_define_false_aliases(
    backend: Literal["argparse", "click"],
) -> None:
    @params(
        disable_cache=Param(
            boolean_mode="dual",
            negative_flags=("-E", "--enable-cache"),
        )
    )
    def command(*, disable_cache: bool = False) -> bool:
        return disable_cache

    parser = Interfacy(backend=backend, sys_exit_enabled=False)
    parser.add_command(command)

    assert parser.run(args=["--disable-cache"]) is True
    assert parser.run(args=["--enable-cache"]) is False
    assert parser.run(args=["-E"]) is False


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_none_default_auto_mode_preserves_tri_state(
    backend: Literal["argparse", "click"],
) -> None:
    def command(*, enabled: bool | None = None) -> bool | None:
        return enabled

    parser = Interfacy(backend=backend, sys_exit_enabled=False)
    parser.add_command(command)

    assert parser.run(args=[]) is None
    assert parser.run(args=["--enabled"]) is True
    assert parser.run(args=["--no-enabled"]) is False


@pytest.mark.parametrize(
    ("default", "mode", "message"),
    [
        (True, BooleanMode.POSITIVE_ONLY, "does not default to False"),
        (False, BooleanMode.NEGATIVE_ONLY, "does not default to True"),
    ],
)
def test_one_way_mode_must_change_the_default(
    default: bool,
    mode: BooleanMode,
    message: str,
) -> None:
    def command(*, enabled: bool = default) -> bool:
        return enabled

    parser = Interfacy(sys_exit_enabled=False)
    parser.add_command(command, parameter_settings={"enabled": Param(boolean_mode=mode)})

    with pytest.raises(ConfigurationError, match=message):
        parser.build_parser_schema()


def test_boolean_settings_reject_non_boolean_parameter() -> None:
    def command(*, count: int = 0) -> int:
        return count

    parser = Interfacy(sys_exit_enabled=False)
    parser.add_command(
        command,
        parameter_settings={"count": Param(boolean_mode="dual")},
    )

    with pytest.raises(ConfigurationError, match="only configure boolean parameter 'count'"):
        parser.build_parser_schema()


def test_negative_mode_requires_derivable_or_explicit_negative_flag() -> None:
    def command(*, enabled: bool = True) -> bool:
        return enabled

    parser = Interfacy(sys_exit_enabled=False)
    parser.add_command(
        command,
        parameter_settings={"enabled": Param(flags="-e")},
    )

    with pytest.raises(ConfigurationError, match=r"requires Param\.negative_flags"):
        parser.build_parser_schema()


def test_positive_only_mode_rejects_negative_flags() -> None:
    def command(*, enabled: bool = False) -> bool:
        return enabled

    parser = Interfacy(sys_exit_enabled=False)
    parser.add_command(
        command,
        parameter_settings={
            "enabled": Param(
                boolean_mode="positive_only",
                negative_flags="--disabled",
            )
        },
    )

    with pytest.raises(ConfigurationError, match="cannot define negative flags"):
        parser.build_parser_schema()

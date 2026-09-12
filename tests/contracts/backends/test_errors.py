from typing import Any

import pytest

from interfacy import ConfigurationError, ExitCode, Interfacy, InterfacyError, UsageError
from interfacy.naming import DefaultFlagStrategy
from interfacy.plugins import AfterParseContext, InterfacyPlugin


@pytest.fixture(params=["argparse", "click"])
def parser(request: pytest.FixtureRequest) -> Interfacy:
    parser_kwargs: dict[str, Any] = {
        "flag_strategy": DefaultFlagStrategy(style="required_positional"),
        "full_error_traceback": True,
        "help_layout": None,
        "print_result": False,
    }
    if request.param == "argparse":
        return Interfacy(backend="argparse", **parser_kwargs)

    pytest.importorskip("click")

    return Interfacy(backend="click", **parser_kwargs)


def test_invoke_returns_integer_command_data(parser: Interfacy) -> None:
    def count() -> int:
        return 7

    assert parser.invoke(count, args=[]) == 7


def test_invoke_raises_usage_error_without_rendering(
    parser: Interfacy,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def greet(name: str) -> str:
        return f"hello {name}"

    with pytest.raises(UsageError):
        parser.invoke(greet, args=[])

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_invoke_raises_configuration_error(parser: Interfacy) -> None:
    with pytest.raises(ConfigurationError, match="No commands were provided"):
        parser.invoke(args=[])


def test_invoke_propagates_command_exception(parser: Interfacy) -> None:
    def fail() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        parser.invoke(fail, args=[])


def test_invoke_propagates_interrupt_without_cli_callback(parser: Interfacy) -> None:

    def interrupt() -> None:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        parser.invoke(interrupt, args=[])


def test_invoke_propagates_explicit_system_exit(parser: Interfacy) -> None:
    def abort() -> None:
        raise SystemExit(7)

    with pytest.raises(SystemExit) as error:
        parser.invoke(abort, args=[])

    assert error.value.code == 7


def test_run_prints_integer_data_then_exits_successfully(
    parser: Interfacy,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser.apply_setup(print_result=True)

    def count() -> int:
        return 7

    with pytest.raises(SystemExit) as error:
        parser.run(count, args=[])

    assert error.value.code == ExitCode.SUCCESS
    assert capsys.readouterr().out == "7\n"


def test_run_maps_usage_failure_and_renders_usage(
    parser: Interfacy,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def greet(name: str) -> str:
        return f"hello {name}"

    with pytest.raises(SystemExit) as error:
        parser.run(greet, args=[])

    assert error.value.code == ExitCode.USAGE
    assert "usage:" in capsys.readouterr().err.lower()


def test_run_maps_configuration_failure(parser: Interfacy) -> None:
    with pytest.raises(SystemExit) as error:
        parser.run(args=[])

    assert error.value.code == ExitCode.CONFIGURATION


def test_run_maps_command_failure(parser: Interfacy) -> None:
    def fail() -> None:
        raise ValueError("boom")

    with pytest.raises(SystemExit) as error:
        parser.run(fail, args=[])

    assert error.value.code == ExitCode.COMMAND_FAILED


def test_run_maps_internal_framework_failure(parser: Interfacy) -> None:
    class BrokenPlugin(InterfacyPlugin):
        def after_parse(
            self,
            context: AfterParseContext,
            namespace: dict[str, Any],
        ) -> dict[str, Any]:
            del context, namespace
            raise InterfacyError("broken plugin")

    def command() -> None:
        return None

    parser.add_plugin(BrokenPlugin())
    with pytest.raises(SystemExit) as error:
        parser.run(command, args=[])

    assert error.value.code == ExitCode.INTERNAL


def test_run_maps_interrupt_and_calls_handler(parser: Interfacy) -> None:
    callbacks: list[str] = []
    runner = Interfacy(
        backend=parser.backend,
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        on_interrupt=lambda error: callbacks.append(type(error).__name__),
        silent_interrupt=True,
    )

    def interrupt() -> None:
        raise KeyboardInterrupt

    with pytest.raises(SystemExit) as error:
        runner.run(interrupt, args=[])

    assert error.value.code == ExitCode.INTERRUPTED
    assert callbacks == ["KeyboardInterrupt"]


def test_run_maps_help_to_success(parser: Interfacy) -> None:
    def command() -> None:
        return None

    with pytest.raises(SystemExit) as error:
        parser.run(command, args=["--help"])

    assert error.value.code == ExitCode.SUCCESS


def test_invoke_raises_usage_error_on_invalid_enum(parser: Interfacy) -> None:
    from enum import Enum

    class Color(Enum):
        RED = "red"
        BLUE = "blue"

    def set_color(c: Color) -> Color:
        return c

    with pytest.raises(UsageError):
        parser.invoke(set_color, args=["yellow"])

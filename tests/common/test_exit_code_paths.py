import pytest

from interfacy.argparse_backend import Argparser
from interfacy.core import ExitCode, InterfacyParser
from interfacy.exceptions import ConfigurationError, DuplicateCommandError, PipeInputError
from interfacy.naming import DefaultFlagStrategy


@pytest.fixture(params=["argparse", "click"])
def backend(request: pytest.FixtureRequest) -> str:
    if request.param == "click":
        pytest.importorskip("click")

    return request.param


def _build_parser(
    *,
    backend: str,
    sys_exit_enabled: bool,
    **kwargs: object,
) -> InterfacyParser:
    parser_kwargs = {
        "flag_strategy": DefaultFlagStrategy(style="required_positional"),
        "sys_exit_enabled": sys_exit_enabled,
        "full_error_traceback": True,
        "help_layout": None,
        "print_result": False,
        **kwargs,
    }
    if backend == "argparse":
        return Argparser(**parser_kwargs)

    from interfacy.click_backend import ClickParser

    return ClickParser(**parser_kwargs)


def _capture_exit_calls(parser: InterfacyParser) -> list[ExitCode]:
    calls: list[ExitCode] = []

    def _exit(code: ExitCode) -> ExitCode:
        calls.append(code)
        return code

    parser.exit = _exit  # type: ignore[method-assign]

    return calls


def test_success_path_returns_value_and_emits_success_exit_code(backend: str) -> None:
    parser = _build_parser(backend=backend, sys_exit_enabled=False)
    exit_calls = _capture_exit_calls(parser)

    def greet(name: str) -> str:
        return f"hello {name}"

    result = parser.run(greet, args=["Ada"])

    assert result == "hello Ada"
    assert exit_calls == [ExitCode.SUCCESS]


def test_duplicate_registration_maps_to_err_parsing_exit_code(backend: str) -> None:
    parser = _build_parser(backend=backend, sys_exit_enabled=False)
    exit_calls = _capture_exit_calls(parser)

    def duplicate() -> None:
        return None

    result = parser.run(duplicate, duplicate, args=[])

    assert isinstance(result, DuplicateCommandError)
    assert exit_calls == [ExitCode.ERR_PARSING]


def test_no_commands_maps_to_parsing_exit_code(backend: str) -> None:
    parser = _build_parser(backend=backend, sys_exit_enabled=False)
    exit_calls = _capture_exit_calls(parser)

    result = parser.run(args=[])

    assert isinstance(result, ConfigurationError)
    assert exit_calls == [ExitCode.ERR_PARSING]


def test_pipe_input_error_maps_to_runtime_internal_exit_code(
    backend: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = _build_parser(backend=backend, sys_exit_enabled=False)
    exit_calls = _capture_exit_calls(parser)

    def pair(a: str, b: str) -> tuple[str, str]:
        return a, b

    parser.add_command(pair, pipe_targets=("a", "b"))
    monkeypatch.setattr("interfacy.core.read_piped", lambda: "only-one-chunk")

    result = parser.run(args=[])

    assert isinstance(result, PipeInputError)
    assert exit_calls == [ExitCode.ERR_RUNTIME_INTERNAL]


def test_user_exception_maps_to_runtime_exit_code(backend: str) -> None:
    parser = _build_parser(backend=backend, sys_exit_enabled=False)
    exit_calls = _capture_exit_calls(parser)

    def boom() -> None:
        raise ValueError("boom")

    result = parser.run(boom, args=[])

    assert isinstance(result, ValueError)
    assert exit_calls == [ExitCode.ERR_RUNTIME]


def test_keyboard_interrupt_maps_to_interrupted_exit_code(backend: str) -> None:
    parser = _build_parser(backend=backend, sys_exit_enabled=False, silent_interrupt=True)
    exit_calls = _capture_exit_calls(parser)

    def interrupt() -> None:
        raise KeyboardInterrupt()

    result = parser.run(interrupt, args=[])

    assert isinstance(result, KeyboardInterrupt)
    assert exit_calls == [ExitCode.INTERRUPTED]


def test_system_exit_is_returned_when_sys_exit_is_disabled(backend: str) -> None:
    parser = _build_parser(backend=backend, sys_exit_enabled=False)
    exit_calls = _capture_exit_calls(parser)

    def abort() -> None:
        raise SystemExit(7)

    result = parser.run(abort, args=[])

    assert isinstance(result, SystemExit)
    assert result.code == 7
    assert exit_calls == []


def test_system_exit_is_reraised_when_sys_exit_is_enabled(backend: str) -> None:
    parser = _build_parser(backend=backend, sys_exit_enabled=True)

    def abort() -> None:
        raise SystemExit(7)

    with pytest.raises(SystemExit) as excinfo:
        parser.run(abort, args=[])

    assert excinfo.value.code == 7


def test_click_exit_is_normalized_to_system_exit_when_sys_exit_is_disabled() -> None:
    click = pytest.importorskip("click")
    parser = _build_parser(backend="click", sys_exit_enabled=False)

    def abort() -> None:
        raise click.exceptions.Exit(5)

    result = parser.run(abort, args=[])

    assert isinstance(result, SystemExit)
    assert result.code == 5


def test_click_usage_error_from_command_maps_to_parse_failure(capsys: pytest.CaptureFixture[str]):
    click = pytest.importorskip("click")
    parser = _build_parser(backend="click", sys_exit_enabled=False)
    exit_calls = _capture_exit_calls(parser)

    def abort() -> None:
        raise click.UsageError("bad usage")

    result = parser.run(abort, args=[])

    assert isinstance(result, click.UsageError)
    assert exit_calls == [ExitCode.ERR_PARSING]
    assert "bad usage" in capsys.readouterr().err


def test_click_parse_usage_error_returns_system_exit(capsys: pytest.CaptureFixture[str]):
    parser = _build_parser(backend="click", sys_exit_enabled=False)

    def greet(name: str) -> str:
        return f"hello {name}"

    result = parser.run(greet, args=["--unknown"])

    assert isinstance(result, SystemExit)
    assert result.code == 2
    assert "No such option" in capsys.readouterr().err

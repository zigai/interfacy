import pytest

from interfacy.argparse_backend import Argparser
from interfacy.naming import DefaultFlagStrategy


def _demo(name: str = "world") -> str:
    return f"hello {name}"


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_help_system_exit_zero_is_not_logged_as_error(parser, capsys) -> None:
    parser.add_command(_demo)

    result = parser.run(args=["--help"])

    assert isinstance(result, SystemExit)
    assert result.code == 0

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "usage:" in combined.lower()
    assert "[interfacy] SystemExit" not in combined


def test_parse_error_system_exit_is_not_logged(argparse_req_pos, capsys) -> None:
    argparse_req_pos.add_command(_demo)

    result = argparse_req_pos.run(args=["--missing-flag"])

    assert isinstance(result, SystemExit)
    assert result.code == 2

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "[interfacy] SystemExit" not in combined


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_command_raised_system_exit_is_respected_without_logging(parser, capsys) -> None:
    def abort() -> None:
        raise SystemExit(7)

    parser.add_command(abort)

    result = parser.run(args=[])

    assert isinstance(result, SystemExit)
    assert result.code == 7

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "[interfacy] SystemExit" not in combined


def test_help_exits_with_zero_when_sys_exit_enabled() -> None:
    parser = Argparser(
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        sys_exit_enabled=True,
        full_error_traceback=True,
        help_layout=None,
        print_result=False,
    )
    parser.add_command(_demo)

    with pytest.raises(SystemExit) as excinfo:
        parser.run(args=["--help"])

    assert excinfo.value.code == 0

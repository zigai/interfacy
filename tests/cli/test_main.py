from __future__ import annotations

from pathlib import Path
import sys

import pytest

from interfacy.cli.main import ExitCode, main, resolve_target


def _write_module(path: Path, source: str) -> None:
    path.write_text(source, encoding="utf-8")


def test_resolve_target_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = tmp_path / "sample_mod.py"
    _write_module(
        module_path,
        "\n".join(
            [
                "def hello():",
                "    return 'ok'",
                "",
            ]
        ),
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    target = resolve_target("sample_mod:hello")
    assert callable(target)
    assert target() == "ok"


def test_resolve_target_file_path(tmp_path: Path) -> None:
    module_path = tmp_path / "entry.py"
    _write_module(
        module_path,
        "\n".join(
            [
                "def hello():",
                "    return 'ok'",
                "",
            ]
        ),
    )

    target = resolve_target(f"{module_path}:hello")
    assert callable(target)
    assert target() == "ok"


def test_main_invalid_target_missing_colon(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["nosuchtarget"])

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "Target must be in the form" in captured.err


def test_main_invalid_target_file_missing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing_path = tmp_path / "missing.py"
    with pytest.raises(SystemExit) as excinfo:
        main([f"{missing_path}:main"])

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "Python file not found" in captured.err


def test_main_invalid_target_attribute_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module_path = tmp_path / "mod.py"
    _write_module(
        module_path,
        "\n".join(
            [
                "def exists():",
                "    return 'ok'",
                "",
            ]
        ),
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(SystemExit) as excinfo:
        main(["mod:missing"])

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "Symbol 'missing' not found" in captured.err


def test_main_config_paths_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    env_path = tmp_path / "custom.toml"
    monkeypatch.setenv("INTERFACY_CONFIG", str(env_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

    result = main(["--config-paths"])
    assert result == ExitCode.SUCCESS

    captured = capsys.readouterr()
    lines = [line.strip() for line in captured.out.splitlines() if line.strip()]
    assert lines == [
        str(env_path),
        str(tmp_path / ".interfacy.toml"),
        str(tmp_path / "home" / ".config" / "interfacy" / "config.toml"),
    ]


def test_main_passthrough_double_dash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module_path = tmp_path / "mod.py"
    _write_module(
        module_path,
        "\n".join(
            [
                "from interfacy.argparse_backend import Argparser",
                "",
                "def echo(msg: str) -> str:",
                "    return msg",
                "",
                "parser = Argparser(sys_exit_enabled=False, print_result=False)",
                "parser.add_command(echo)",
                "",
            ]
        ),
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    result = main([f"{module_path}:parser", "--", "echo", "hi"])
    assert result == ExitCode.SUCCESS


def test_main_applies_config_to_parser_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module_path = tmp_path / "mod.py"
    _write_module(
        module_path,
        "\n".join(
            [
                "from interfacy.argparse_backend import Argparser",
                "",
                "def echo(msg: str) -> str:",
                "    return msg",
                "",
                "parser = Argparser(sys_exit_enabled=False, print_result=False, allow_args_from_file=True)",
                "parser.add_command(echo)",
                "",
            ]
        ),
    )
    config_path = tmp_path / ".interfacy.toml"
    config_path.write_text(
        "\n".join(
            [
                "[behavior]",
                "print_result = true",
                "allow_args_from_file = false",
                "",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delenv("INTERFACY_CONFIG", raising=False)

    result = main([f"{module_path}:parser", "echo", "hi"])
    assert result == ExitCode.SUCCESS

    module_name = f"interfacy_entry_{module_path.stem}_{abs(hash(str(module_path)))}"
    module = sys.modules[module_name]
    parser_obj = module.parser
    assert parser_obj.display_result is True
    assert parser_obj.allow_args_from_file is False


def test_main_config_print_result_for_function_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module_path = tmp_path / "mod.py"
    _write_module(
        module_path,
        "\n".join(
            [
                "def echo(msg: str) -> str:",
                "    return msg",
                "",
            ]
        ),
    )
    config_path = tmp_path / ".interfacy.toml"
    config_path.write_text(
        "\n".join(
            [
                "[behavior]",
                "print_result = true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delenv("INTERFACY_CONFIG", raising=False)

    with pytest.raises(SystemExit) as excinfo:
        main([f"{module_path}:echo", "hi"])

    assert excinfo.value.code == ExitCode.SUCCESS
    captured = capsys.readouterr()
    assert "hi" in captured.out

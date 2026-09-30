import sys

import pytest

from interfacy import Interfacy
from interfacy.runtime.process import (
    derive_process_title,
    set_process_title,
)


def _noop() -> None:
    return None


def test_derive_process_title_uses_basename_and_strips_windows_suffix() -> None:
    assert derive_process_title("/tmp/.venv/bin/my-cli") == "my-cli"
    assert derive_process_title(r"C:\tools\my-cli.exe") == "my-cli"


def test_derive_process_title_falls_back_for_empty_input() -> None:
    assert derive_process_title("") == "interfacy"


def test_set_process_title_prefers_setproctitle_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "interfacy.runtime.process.setproctitle",
        lambda title: calls.append(("setproctitle", title)),
    )

    assert set_process_title("my-cli") is True
    assert calls == [("setproctitle", "my-cli")]


def test_set_process_title_does_not_fallback_when_setproctitle_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    def _raise_runtime_error(title: str) -> None:
        calls.append(("setproctitle", title))
        raise RuntimeError("boom")

    monkeypatch.setattr("interfacy.runtime.process.setproctitle", _raise_runtime_error)

    assert set_process_title("my-cli") is False
    assert calls == [("setproctitle", "my-cli")]


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_parsers_set_runtime_process_title_on_run(
    parser: Interfacy,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    titles: list[str] = []

    monkeypatch.setattr("interfacy.runtime.process.setproctitle", titles.append)
    monkeypatch.setattr(sys, "argv", ["/home/user/.local/bin/acme-tool"])
    parser.add_command(_noop)

    with pytest.raises(SystemExit) as exc_info:
        parser.run(args=[])

    assert exc_info.value.code == 0
    assert titles == ["acme-tool"]

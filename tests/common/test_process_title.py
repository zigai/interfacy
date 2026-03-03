import pytest

from interfacy.core import InterfacyParser
from interfacy.process_title import (
    derive_process_title,
    set_process_title,
    set_process_title_from_argv,
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
        "interfacy.process_title._set_process_title_with_setproctitle",
        lambda title: calls.append(("setproctitle", title)) or True,
    )

    assert set_process_title("my-cli") is True
    assert calls == [("setproctitle", "my-cli")]


def test_set_process_title_does_not_fallback_when_setproctitle_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "interfacy.process_title._set_process_title_with_setproctitle",
        lambda title: calls.append(("setproctitle", title)) or False,
    )

    assert set_process_title("my-cli") is False
    assert calls == [("setproctitle", "my-cli")]


def test_set_process_title_from_argv_uses_derived_name(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    monkeypatch.setattr(
        "interfacy.process_title.set_process_title",
        lambda title: seen.append(title) or True,
    )

    assert set_process_title_from_argv("/home/user/.local/bin/acme-tool") is True
    assert seen == ["acme-tool"]


@pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
def test_parsers_set_runtime_process_title_on_run(
    parser: InterfacyParser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[str] = []

    monkeypatch.setattr(
        InterfacyParser,
        "_set_runtime_process_title",
        lambda self: called.append(type(self).__name__),
    )
    parser.add_command(_noop)

    parser.run(args=[])

    assert len(called) == 1

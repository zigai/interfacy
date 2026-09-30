import pytest

from tests.fixtures.terminal import freeze_terminal


@pytest.fixture
def fixed_terminal_width(monkeypatch: pytest.MonkeyPatch) -> None:
    freeze_terminal(monkeypatch, 80)

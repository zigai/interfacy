from pathlib import Path

import pytest


def test_ruff_pre_commit_hook_does_not_ignore_failures() -> None:
    config_path = Path(__file__).resolve().parents[3] / ".pre-commit-config.yaml"
    if not config_path.exists():
        pytest.skip(".pre-commit-config.yaml not present in distribution")
    config = config_path.read_text(encoding="utf-8")

    assert "--exit-zero" not in config

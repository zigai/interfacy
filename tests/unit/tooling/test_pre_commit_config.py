from pathlib import Path

import pytest
import yaml


def test_ruff_pre_commit_hook_does_not_ignore_failures() -> None:
    config_path = Path(__file__).resolve().parents[3] / ".pre-commit-config.yaml"
    if not config_path.exists():
        pytest.skip(".pre-commit-config.yaml not present in distribution")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    hooks = [
        hook for repo in config["repos"] for hook in repo["hooks"] if hook["id"] == "ruff-check"
    ]

    assert hooks, "Ruff lint hook must be configured"

    for hook in hooks:
        assert "--exit-zero" not in hook.get("args", [])

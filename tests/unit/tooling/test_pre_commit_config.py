from pathlib import Path


def test_ruff_pre_commit_hook_does_not_ignore_failures() -> None:
    config = Path(".pre-commit-config.yaml").read_text(encoding="utf-8")

    assert "--exit-zero" not in config

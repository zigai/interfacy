from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

EXAMPLE_CASES: tuple[
    tuple[str, tuple[str, ...], str, str | None, tuple[str, ...], tuple[str, ...]],
    ...,
] = (
    (
        "example1_boolean_flags.py",
        (),
        r"^StandardLayout$",
        r"^ArgparseLayout$",
        ("[default:",),
        ("Defaults to",),
    ),
    (
        "example2_twitch_scraper.py",
        (),
        r"^StandardLayout$",
        r"^ArgparseLayout$",
        ("[default:",),
        ("Defaults to",),
    ),
    (
        "example3_video_compression.py",
        (),
        r"^StandardLayout$",
        r"^ArgparseLayout$",
        ("[default:",),
        ("Defaults to",),
    ),
    (
        "example4_layout_stress_test.py",
        ("--limit", "1"),
        r"^layout=StandardLayout,",
        r"^layout=ArgparseLayout,",
        ("Show this help message and exit",),
        ("Print help",),
    ),
)


def _extract_section(text: str, start_pattern: str, end_pattern: str | None) -> str:
    lines = text.splitlines()
    start_re = re.compile(start_pattern)
    end_re = re.compile(end_pattern) if end_pattern is not None else None

    start_idx = next((i for i, line in enumerate(lines) if start_re.search(line)), None)
    if start_idx is None:
        msg = f"Could not locate section start pattern: {start_pattern!r}"
        raise AssertionError(msg)

    end_idx = len(lines)
    if end_re is not None:
        for i in range(start_idx + 1, len(lines)):
            if end_re.search(lines[i]):
                end_idx = i
                break

    return "\n".join(lines[start_idx:end_idx])


@pytest.mark.parametrize(
    ("script_name", "args", "section_start", "section_end", "expected_contains", "expected_absent"),
    EXAMPLE_CASES,
)
def test_layout_examples_render_standard_layout_semantics(
    script_name: str,
    args: tuple[str, ...],
    section_start: str,
    section_end: str | None,
    expected_contains: tuple[str, ...],
    expected_absent: tuple[str, ...],
) -> None:
    script_path = REPO_ROOT / script_name
    result = subprocess.run(
        [sys.executable, str(script_path), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    section = _extract_section(combined, section_start, section_end)
    for token in expected_contains:
        assert token in section
    for token in expected_absent:
        assert token not in section

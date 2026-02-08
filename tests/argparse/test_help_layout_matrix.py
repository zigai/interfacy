from __future__ import annotations

import copy
import os
import re
import shutil
from enum import Enum
from typing import Literal

import pytest

from interfacy import Argparser, CommandGroup
from interfacy.appearance import (
    Aligned,
    AlignedTyped,
    ArgparseLayout,
    ClapLayout,
    HelpLayout,
    InterfacyLayout,
    Modern,
)


class Strategy(Enum):
    FAST = "fast"
    SAFE = "safe"
    BALANCED = "balanced"


def dense_parameters(
    input_path: str,
    output_path: str,
    *,
    mode: Literal["fast", "safe", "balanced"] = "balanced",
    strategy: Strategy = Strategy.BALANCED,
    retries: int = 3,
    ratio: float = 0.75,
    tags: list[str] | None = None,
    bounds: tuple[int, int] = (1, 10),
    dry_run: bool = False,
    force: bool = True,
    note: str = "use --mode for behavior selection",
    banner: str = "THIS DEFAULT IS INTENTIONALLY VERY LONG TO EXCEED THE DEFAULT COLUMN WIDTH",
) -> dict[str, object]:
    """Exercise choices, defaults, tuples, and long descriptions."""
    return {
        "input_path": input_path,
        "output_path": output_path,
        "mode": mode,
        "strategy": strategy,
        "retries": retries,
        "ratio": ratio,
        "tags": tags,
        "bounds": bounds,
        "dry_run": dry_run,
        "force": force,
        "note": note,
        "banner": banner,
    }


def path_ops(
    source: str,
    target: str,
    *extras: str,
    level: int = 2,
    dry_run: bool = False,
    tag: str | None = None,
) -> dict[str, object]:
    """Mix positionals, varargs, and keyword-only options."""
    return {
        "source": source,
        "target": target,
        "extras": extras,
        "level": level,
        "dry_run": dry_run,
        "tag": tag,
    }


def keyword_only_options(
    *,
    region: str = "us-east-1",
    timeout_s: float = 1.5,
    include_hidden: bool = False,
    names: list[str] | None = None,
) -> dict[str, object]:
    """Keyword-only options with defaults for alignment testing."""
    return {
        "region": region,
        "timeout_s": timeout_s,
        "include_hidden": include_hidden,
        "names": names,
    }


class ReportTool:
    """Class-based commands to test subcommand help layout and epilog alignment."""

    def __init__(
        self,
        output_dir: str,
        *,
        title: str = "Report",
        compact: bool = False,
        max_rows: int = 1000,
    ) -> None:
        self.output_dir = output_dir
        self.title = title
        self.compact = compact
        self.max_rows = max_rows

    def summarize(
        self,
        input_path: str,
        *,
        fmt: Literal["md", "json", "txt"] = "md",
        include: list[str] | None = None,
        top_k: int = 5,
    ) -> dict[str, object]:
        """Summarize data with list and literal choices."""
        return {"input_path": input_path, "fmt": fmt, "include": include, "top_k": top_k}

    def compare(
        self,
        left: str,
        right: str,
        *,
        mode: Literal["strict", "loose"] = "strict",
        color: bool = True,
    ) -> dict[str, object]:
        """Compare two sources; default True boolean should show --no-color."""
        return {"left": left, "right": right, "mode": mode, "color": color}


class GroupArgs:
    """Group-level arguments to test nested subparser alignment."""

    def __init__(
        self,
        workspace: str,
        *,
        region: str = "us-east-1",
        retries: int = 2,
        debug: bool = False,
    ) -> None:
        self.workspace = workspace
        self.region = region
        self.retries = retries
        self.debug = debug


def cache_clean(path: str, *, age_days: int = 30, force: bool = False) -> dict[str, object]:
    """Clean old cache entries with defaults and bool flags."""
    return {"path": path, "age_days": age_days, "force": force}


def cache_prune(
    keys: list[str] | None = None,
    *,
    limit: int = 100,
    dry_run: bool = True,
) -> dict[str, object]:
    """Prune cache keys; bool default True should show --no-dry-run."""
    return {"keys": keys, "limit": limit, "dry_run": dry_run}


def build_group() -> CommandGroup:
    ops = CommandGroup(
        "ops",
        description="Operations group for nested command layout checks.",
        aliases=("op",),
    ).with_args(GroupArgs)
    ops.add_command(cache_prune, aliases=("prune",))

    nested = CommandGroup(
        "nested-tools",
        description="Nested subgroup with a longer name to test alignment.",
        aliases=("nested",),
    )
    nested.add_command(cache_clean, aliases=("clean",))
    ops.add_group(nested)
    return ops


def build_stress_parser(layout: HelpLayout, parser: Argparser) -> Argparser:
    parser.description = "Interfacy layout stress test (multiple command shapes)."
    parser.help_layout = layout
    parser.help_layout.flag_generator = parser.flag_strategy
    parser.help_layout.name_registry = parser.name_registry
    parser.sys_exit_enabled = False
    parser.print_result = False
    parser.add_command(dense_parameters)
    parser.add_command(path_ops)
    parser.add_command(keyword_only_options)
    parser.add_command(ReportTool)
    parser.add_command(build_group())
    return parser


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def freeze_terminal(monkeypatch: pytest.MonkeyPatch, width: int) -> None:
    size = os.terminal_size((width, 24))
    monkeypatch.setattr(os, "get_terminal_size", lambda *args, **kwargs: size)
    monkeypatch.setattr(shutil, "get_terminal_size", lambda *args, **kwargs: size)
    monkeypatch.setenv("COLUMNS", str(width))


def render_help_for_args(
    layout_cls: type[HelpLayout],
    args: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Argparser,
    width: int = 80,
) -> str:
    freeze_terminal(monkeypatch, width)
    parser = build_stress_parser(layout_cls(), copy.deepcopy(argparse_req_pos))
    try:
        parser.run(args=args)
    except SystemExit:
        pass
    out = capsys.readouterr()
    return out.out + out.err


LAYOUTS: tuple[type[HelpLayout], ...] = (
    InterfacyLayout,
    Aligned,
    AlignedTyped,
    Modern,
    ArgparseLayout,
    ClapLayout,
)


@pytest.mark.parametrize("layout_cls", LAYOUTS)
def test_root_help_contains_usage_options_and_commands_sections(
    layout_cls: type[HelpLayout],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Argparser,
) -> None:
    help_text = strip_ansi(
        render_help_for_args(layout_cls, ["--help"], monkeypatch, capsys, argparse_req_pos)
    )
    lower = help_text.lower()

    assert "usage:" in lower
    assert re.search(r"(?m)^options?:$", lower)
    assert re.search(r"(?m)^commands?:$", lower)
    assert len(re.findall(r"(?m)^commands:$", lower)) == 1


@pytest.mark.parametrize(
    "layout_cls",
    (InterfacyLayout, Aligned, AlignedTyped, Modern, ArgparseLayout),
)
def test_usage_boolean_tokens_use_primary_form_without_alternation(
    layout_cls: type[HelpLayout],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Argparser,
) -> None:
    help_text = strip_ansi(
        render_help_for_args(
            layout_cls, ["path-ops", "--help"], monkeypatch, capsys, argparse_req_pos
        )
    )
    assert "--dry-run" in help_text
    assert "| --dry-run" not in help_text
    assert "-d | --dry-run" not in help_text


@pytest.mark.parametrize(
    "layout_cls",
    (InterfacyLayout, Aligned, AlignedTyped, Modern, ArgparseLayout),
)
def test_usage_subcommand_choices_show_canonical_names_without_aliases(
    layout_cls: type[HelpLayout],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Argparser,
) -> None:
    help_text = strip_ansi(
        render_help_for_args(
            layout_cls,
            ["ops", "workspace", "--help"],
            monkeypatch,
            capsys,
            argparse_req_pos,
        )
    )
    assert "{nested-tools,cache-prune}" in help_text
    assert "{nested-tools,nested,cache-prune,prune}" not in help_text
    assert "{nested-tools,cache-prune,prune}" not in help_text


def test_argparse_layout_root_commands_rows_do_not_include_choices_header_line(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Argparser,
) -> None:
    help_text = strip_ansi(
        render_help_for_args(ArgparseLayout, ["--help"], monkeypatch, capsys, argparse_req_pos)
    )
    assert "commands:" in help_text
    assert (
        "commands:\n  {dense-parameters,path-ops,keyword-only-options,report-tool,ops}"
        not in help_text
    )
    assert "dense-parameters" in help_text
    assert "Exercise choices, defaults, tuples, and long descriptions." in help_text


def test_argparse_layout_command_descriptions_align_with_option_help_column(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Argparser,
) -> None:
    help_text = strip_ansi(
        render_help_for_args(ArgparseLayout, ["--help"], monkeypatch, capsys, argparse_req_pos)
    )
    lines = help_text.splitlines()
    help_line = next(line for line in lines if "--help" in line and "show this help" in line)
    dense_line = next(line for line in lines if line.strip().startswith("dense-parameters"))
    path_line = next(line for line in lines if line.strip().startswith("path-ops"))

    help_idx = help_line.index("show this help message and exit")
    dense_idx = dense_line.index("Exercise choices, defaults, tuples, and long descriptions.")
    path_idx = path_line.index("Mix positionals, varargs, and keyword-only options.")

    assert dense_idx == help_idx
    assert path_idx == help_idx
    assert help_idx >= 30


def test_usage_wrapping_is_width_sensitive_for_template_layouts(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Argparser,
) -> None:
    narrow = strip_ansi(
        render_help_for_args(
            InterfacyLayout,
            ["dense-parameters", "--help"],
            monkeypatch,
            capsys,
            argparse_req_pos,
            width=60,
        )
    )
    wide = strip_ansi(
        render_help_for_args(
            InterfacyLayout,
            ["dense-parameters", "--help"],
            monkeypatch,
            capsys,
            argparse_req_pos,
            width=140,
        )
    )

    def usage_block_line_count(text: str) -> int:
        lines = text.splitlines()
        idx = next(i for i, line in enumerate(lines) if line.lower().startswith("usage:"))
        count = 1
        j = idx + 1
        while j < len(lines) and lines[j].startswith(" "):
            count += 1
            j += 1
        return count

    assert usage_block_line_count(narrow) > usage_block_line_count(wide)


def test_argparse_layout_long_option_help_stays_inline_with_readable_gap(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Argparser,
) -> None:
    help_text = strip_ansi(
        render_help_for_args(
            ArgparseLayout, ["dense-parameters", "--help"], monkeypatch, capsys, argparse_req_pos
        )
    )
    lines = help_text.splitlines()
    bounds_line = next(line for line in lines if "-b, --bounds BOUNDS BOUNDS" in line)
    assert "Defaults to (1, 10)." in bounds_line


@pytest.mark.parametrize(
    ("args", "line_selector", "help_token", "row_token"),
    (
        (
            ["path-ops", "--help"],
            "-l, --level LEVEL",
            "show this help message and exit",
            "Defaults to 2.",
        ),
        (
            ["report-tool", "output-dir", "compare", "--help"],
            "-m, --mode MODE",
            "show this help message and exit",
            "Defaults to strict.",
        ),
        (
            ["ops", "workspace", "cache-prune", "--help"],
            "-l, --limit LIMIT",
            "show this help message and exit",
            "Defaults to 100.",
        ),
    ),
)
def test_argparse_layout_option_help_column_is_consistently_wide(
    args: list[str],
    line_selector: str,
    help_token: str,
    row_token: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Argparser,
) -> None:
    help_text = strip_ansi(
        render_help_for_args(ArgparseLayout, args, monkeypatch, capsys, argparse_req_pos)
    )
    lines = help_text.splitlines()
    help_line = next(line for line in lines if "--help" in line and help_token in line)
    row_line = next(line for line in lines if line_selector in line and row_token in line)

    help_idx = help_line.index(help_token)
    row_idx = row_line.index(row_token)
    assert help_idx == row_idx
    assert help_idx >= 30


def test_clap_layout_default_columns_align_for_long_option_names(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Argparser,
) -> None:
    help_text = strip_ansi(
        render_help_for_args(
            ClapLayout,
            ["keyword-only-options", "--help"],
            monkeypatch,
            capsys,
            argparse_req_pos,
        )
    )
    lines = help_text.splitlines()
    region_line = next(line for line in lines if "--region <REGION>" in line)
    timeout_line = next(line for line in lines if "--timeout-s <TIMEOUT-S>" in line)
    assert region_line.index("[default:") == timeout_line.index("[default:")


def test_clap_layout_default_block_without_description_has_no_extra_leading_gap(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Argparser,
) -> None:
    help_text = strip_ansi(
        render_help_for_args(
            ClapLayout,
            ["keyword-only-options", "--help"],
            monkeypatch,
            capsys,
            argparse_req_pos,
        )
    )
    lines = help_text.splitlines()
    help_line = next(line for line in lines if "--help" in line and "Print help" in line)
    region_line = next(
        line for line in lines if "--region <REGION>" in line and "[default:" in line
    )
    timeout_line = next(
        line for line in lines if "--timeout-s <TIMEOUT-S>" in line and "[default:" in line
    )

    help_desc_idx = help_line.index("Print help")
    region_default_idx = region_line.index("[default:")
    timeout_default_idx = timeout_line.index("[default:")

    assert region_default_idx == timeout_default_idx
    assert timeout_default_idx <= help_desc_idx
    assert timeout_default_idx >= help_desc_idx - 2


def test_clap_layout_no_description_default_aligns_to_help_text_column(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Argparser,
) -> None:
    help_text = strip_ansi(
        render_help_for_args(
            ClapLayout,
            ["ops", "workspace", "cache-prune", "--help"],
            monkeypatch,
            capsys,
            argparse_req_pos,
        )
    )
    lines = help_text.splitlines()
    help_line = next(line for line in lines if "--help" in line and "Print help" in line)
    limit_line = next(line for line in help_text.splitlines() if "--limit <LIMIT>" in line)
    assert limit_line.index("[default:") == help_line.index("Print help")


@pytest.mark.parametrize("layout_cls", (Aligned, AlignedTyped))
def test_aligned_family_command_descriptions_align_with_options_description_column(
    layout_cls: type[HelpLayout],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Argparser,
) -> None:
    help_text = strip_ansi(
        render_help_for_args(
            layout_cls,
            ["report-tool", "output-dir", "--help"],
            monkeypatch,
            capsys,
            argparse_req_pos,
        )
    )
    lines = help_text.splitlines()
    help_line = next(line for line in lines if "--help" in line and "show this help" in line)
    compare_line = next(line for line in lines if line.strip().startswith("compare"))
    summarize_line = next(line for line in lines if line.strip().startswith("summarize"))
    title_line = next(line for line in lines if "--title" in line and "[ Report]" in line)

    help_desc_idx = help_line.index("show this help message and exit")
    compare_desc_idx = compare_line.index("Compare two sources;")
    summarize_desc_idx = summarize_line.index("Summarize data with list and literal choices.")
    title_default_idx = title_line.index("[ Report]")

    assert compare_desc_idx == summarize_desc_idx
    assert compare_desc_idx == title_default_idx
    assert help_desc_idx == title_default_idx


@pytest.mark.parametrize("layout_cls", (Aligned, AlignedTyped))
def test_aligned_family_help_row_uses_default_column_when_default_slot_is_empty(
    layout_cls: type[HelpLayout],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Argparser,
) -> None:
    help_text = strip_ansi(
        render_help_for_args(
            layout_cls,
            ["report-tool", "output-dir", "--help"],
            monkeypatch,
            capsys,
            argparse_req_pos,
        )
    )
    lines = help_text.splitlines()
    help_line = next(line for line in lines if "--help" in line and "show this help" in line)
    title_line = next(line for line in lines if "--title" in line and "[ Report]" in line)

    assert help_line.index("show this help message and exit") == title_line.index("[ Report]")


def test_argparse_commands_descriptions_stay_inline_when_width_is_sufficient(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Argparser,
) -> None:
    help_text = strip_ansi(
        render_help_for_args(
            ArgparseLayout, ["--help"], monkeypatch, capsys, argparse_req_pos, width=100
        )
    )
    assert re.search(
        r"(?m)^\s*dense-parameters\s+Exercise choices, defaults, tuples, and long descriptions\.$",
        help_text,
    )
    assert re.search(
        r"(?m)^\s*path-ops\s+Mix positionals, varargs, and keyword-only options\.$",
        help_text,
    )

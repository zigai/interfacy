from __future__ import annotations

import argparse
import copy
import re
from enum import Enum
from typing import Literal

import pytest
from stdl.st import TextStyle

import interfacy.help.layouts.clap as clap_layout
from interfacy import CommandGroup, ExecutableFlag, Interfacy
from interfacy.common.terminal import strip_ansi
from interfacy.help import (
    Aligned,
    AlignedTyped,
    ArgparseLayout,
    ClapLayout,
    HelpLayout,
    InterfacyLayout,
    Modern,
    StandardLayout,
)
from interfacy.help.colors import ClapColors
from interfacy.naming import DefaultFlagStrategy
from tests.fixtures.terminal import freeze_terminal


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


def build_stress_parser(layout: HelpLayout, parser: Interfacy) -> Interfacy:
    configured = Interfacy(
        backend=parser.backend,
        description="Interfacy layout stress test (multiple command shapes).",
        help_layout=layout,
        flag_strategy=DefaultFlagStrategy(style=parser.metadata["flag_style"]),
    )
    configured.add_command(dense_parameters)
    configured.add_command(path_ops)
    configured.add_command(keyword_only_options)
    configured.add_command(ReportTool)
    configured.add_command(build_group())

    return configured


def render_help_for_args(
    layout_cls: type[HelpLayout],
    args: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Interfacy,
    width: int = 80,
    require_help_success: bool = False,
) -> str:
    freeze_terminal(monkeypatch, width)
    parser = build_stress_parser(layout_cls(), copy.deepcopy(argparse_req_pos))
    if require_help_success:
        with pytest.raises(SystemExit) as excinfo:
            parser.run(args=args)
        assert excinfo.value.code == 0, (
            f"{layout_cls.__name__} {args}: help exited with {excinfo.value.code}"
        )
    else:
        parser.invoke(args=args)
    out = capsys.readouterr()

    return out.out + out.err


LAYOUTS: tuple[type[HelpLayout], ...] = (
    InterfacyLayout,
    Aligned,
    AlignedTyped,
    Modern,
    StandardLayout,
    ArgparseLayout,
    ClapLayout,
)


HELP_ALIGNMENT_MATRIX_ARGS: tuple[tuple[str, ...], ...] = (
    ("--help",),
    ("dense-parameters", "--help"),
    ("path-ops", "--help"),
    ("keyword-only-options", "--help"),
    ("report-tool", "output-dir", "--help"),
    ("report-tool", "output-dir", "compare", "--help"),
    ("report-tool", "output-dir", "summarize", "--help"),
    ("ops", "workspace", "--help"),
    ("ops", "workspace", "cache-prune", "--help"),
    ("ops", "workspace", "nested-tools", "--help"),
    ("ops", "workspace", "nested-tools", "cache-clean", "--help"),
)

ALIGNMENT_SECTION_TITLES: tuple[str, ...] = ("options:", "commands:")

_MULTISPACE_GAP_RE = re.compile(r"\s{2,}")


def _extract_section_rows(help_text: str, section_title: str) -> list[str]:
    lines = help_text.splitlines()
    rows: list[str] = []
    lower_title = section_title.lower()

    for idx, line in enumerate(lines):
        if line.strip().lower() != lower_title:
            continue

        cursor = idx + 1
        while cursor < len(lines):
            current = lines[cursor]
            stripped = current.strip()
            if not stripped:
                break

            if not current.startswith(" ") and stripped.endswith(":"):
                break

            rows.append(current)

            cursor += 1

    return rows


def _extract_payload_start_column(line: str, section_title: str) -> int | None:
    lower_section = section_title.lower()

    for gap in _MULTISPACE_GAP_RE.finditer(line):
        head = line[: gap.start()].rstrip()
        payload = line[gap.end() :]
        if not head or not payload:
            continue

        if lower_section == "options:":
            if "--" not in head:
                continue
            if payload.startswith("-"):
                continue
            return gap.end()

        if lower_section == "commands:":
            if payload.startswith("{"):
                continue

            return gap.end()

    return None


@pytest.mark.parametrize("layout_cls", LAYOUTS)
def test_root_help_contains_usage_options_and_commands_sections(
    layout_cls: type[HelpLayout],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Interfacy,
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
    [
        InterfacyLayout,
        Aligned,
        AlignedTyped,
        Modern,
        StandardLayout,
        ArgparseLayout,
    ],
)
def test_usage_boolean_tokens_use_primary_form_without_alternation(
    layout_cls: type[HelpLayout],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Interfacy,
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
    [
        InterfacyLayout,
        Aligned,
        AlignedTyped,
        Modern,
        StandardLayout,
        ArgparseLayout,
    ],
)
def test_usage_subcommand_choices_show_canonical_names_without_aliases(
    layout_cls: type[HelpLayout],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Interfacy,
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
    argparse_req_pos: Interfacy,
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
    assert "Exercise choices, defaults, tuples, and long" in help_text
    assert "descriptions." in help_text


def test_argparse_layout_command_descriptions_align_with_option_help_column(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Interfacy,
) -> None:
    help_text = strip_ansi(
        render_help_for_args(ArgparseLayout, ["--help"], monkeypatch, capsys, argparse_req_pos)
    )
    lines = help_text.splitlines()
    help_line = next(line for line in lines if "--help" in line and "Show this help" in line)
    dense_line = next(line for line in lines if line.strip().startswith("dense-parameters"))
    path_line = next(line for line in lines if line.strip().startswith("path-ops"))

    help_idx = help_line.index("Show this help message and exit")
    dense_idx = dense_line.index("Exercise choices, defaults, tuples, and long")
    path_idx = path_line.index("Mix positionals, varargs, and")

    assert dense_idx == help_idx
    assert path_idx == help_idx


def test_usage_wrapping_is_width_sensitive_for_template_layouts(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Interfacy,
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
    argparse_req_pos: Interfacy,
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
    [
        (
            ["path-ops", "--help"],
            "-l, --level LEVEL",
            "Show this help message and exit",
            "Defaults to 2.",
        ),
        (
            ["report-tool", "output-dir", "compare", "--help"],
            "-m, --mode MODE",
            "Show this help message and exit",
            "Defaults to strict.",
        ),
        (
            ["ops", "workspace", "cache-prune", "--help"],
            "-l, --limit LIMIT",
            "Show this help message and exit",
            "Defaults to 100.",
        ),
    ],
)
def test_argparse_layout_option_help_column_is_consistently_wide(
    args: list[str],
    line_selector: str,
    help_token: str,
    row_token: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Interfacy,
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


def test_clap_layout_default_columns_align_for_long_option_names(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Interfacy,
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
    argparse_req_pos: Interfacy,
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
    argparse_req_pos: Interfacy,
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


def test_clap_layout_styles_command_names_with_command_name_style(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def deploy() -> None:
        """Deploy the service."""

    def rollback() -> None:
        """Roll back the service."""

    freeze_terminal(monkeypatch, 80)
    monkeypatch.setattr(
        clap_layout,
        "with_style",
        lambda text, style: f"<{style.color}>{text}</{style.color}>",
    )
    colors = ClapColors(command_name_style=TextStyle(color="magenta"))
    app = Interfacy(help_layout=ClapLayout(style=colors), sys_exit_enabled=False)
    app.add_command(deploy)
    app.add_command(rollback)

    app.run(args=["--help"])

    help_text = capsys.readouterr().out
    assert "<magenta>deploy</magenta>" in help_text
    assert "<magenta>rollback</magenta>" in help_text


@pytest.mark.parametrize("layout_cls", [Aligned, AlignedTyped])
def test_aligned_family_command_descriptions_align_with_options_description_column(
    layout_cls: type[HelpLayout],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Interfacy,
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
    help_line = next(line for line in lines if "--help" in line and "Show this help" in line)
    compare_line = next(line for line in lines if line.strip().startswith("compare"))
    summarize_line = next(line for line in lines if line.strip().startswith("summarize"))
    title_line = next(line for line in lines if "--title" in line and "[ Report]" in line)

    help_desc_idx = help_line.index("Show this help message and exit")
    compare_desc_idx = compare_line.index("Compare two sources;")
    summarize_desc_idx = summarize_line.index("Summarize data with list and literal choices.")
    title_default_idx = title_line.index("[ Report]")

    assert compare_desc_idx == summarize_desc_idx
    assert compare_desc_idx == title_default_idx
    assert help_desc_idx == title_default_idx


@pytest.mark.parametrize("layout_cls", [Aligned, AlignedTyped])
def test_aligned_family_help_row_uses_metadata_column_when_option_rows_are_metadata_only(
    layout_cls: type[HelpLayout],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Interfacy,
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
    help_line = next(line for line in lines if "--help" in line and "Show this help" in line)
    title_line = next(line for line in lines if "--title" in line and "[ Report]" in line)

    assert help_line.index("Show this help message and exit") == title_line.index("[ Report]")


def test_argparse_commands_descriptions_stay_inline_when_width_is_sufficient(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Interfacy,
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


@pytest.mark.parametrize("layout_cls", LAYOUTS)
def test_layout_matrix_aligns_help_payload_columns_across_layouts_and_commands(
    layout_cls: type[HelpLayout],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argparse_req_pos: Interfacy,
) -> None:
    failures: list[str] = []
    comparisons = dict.fromkeys(ALIGNMENT_SECTION_TITLES, 0)

    for args in HELP_ALIGNMENT_MATRIX_ARGS:
        help_text = strip_ansi(
            render_help_for_args(
                layout_cls,
                list(args),
                monkeypatch,
                capsys,
                argparse_req_pos,
                require_help_success=True,
            )
        )
        assert "usage:" in help_text.lower(), f"{layout_cls.__name__} {args}: no help rendered"
        for section_title in ALIGNMENT_SECTION_TITLES:
            rows = _extract_section_rows(help_text, section_title)
            payload_columns: list[tuple[str, int]] = []
            for row in rows:
                payload_start = _extract_payload_start_column(row, section_title)
                if payload_start is None:
                    continue

                payload_columns.append((row.strip(), payload_start))

            expect_comparison = (
                section_title == "commands:"
                and args
                in (
                    ("--help",),
                    ("report-tool", "output-dir", "--help"),
                    ("ops", "workspace", "--help"),
                )
            ) or (
                section_title == "options:"
                and args
                not in (
                    ("--help",),
                    ("ops", "workspace", "nested-tools", "--help"),
                )
            )
            if expect_comparison:
                assert len(payload_columns) >= 2, (
                    f"{layout_cls.__name__} {args} {section_title}: "
                    f"expected at least two comparable rows, got {payload_columns}"
                )
            if len(payload_columns) < 2:
                continue
            comparisons[section_title] += 1

            unique_columns = sorted({col for _, col in payload_columns})
            if len(unique_columns) == 1:
                continue

            rendered_rows = ", ".join(f"{col}: {row}" for row, col in payload_columns)
            failures.append(
                "layout="
                f"{layout_cls.__name__} args={list(args)} section={section_title} "
                f"columns={unique_columns} rows=[{rendered_rows}]"
            )

    assert all(comparisons.values()), f"{layout_cls.__name__}: no comparisons in {comparisons}"
    assert not failures, "Misaligned help payload columns:\n" + "\n".join(failures)


def test_standard_layout_hides_option_metavar_by_default() -> None:
    def demo(*, level: int = 2) -> None:
        return None

    parser = Interfacy(backend="argparse", help_layout=StandardLayout(), print_result=False)
    parser.add_command(demo)
    help_text = parser.build_parser().format_help()

    assert "-l, --level LEVEL" not in help_text
    assert "--level" in help_text


def test_standard_layout_renders_defaults_with_bracket_default_block() -> None:
    def demo(*, level: int = 2) -> None:
        """Set output level."""
        return None

    parser = Interfacy(backend="argparse", help_layout=StandardLayout(), print_result=False)
    parser.add_command(demo)
    help_text = parser.build_parser().format_help()
    level_line = next(line for line in help_text.splitlines() if "--level" in line)

    assert "[default: 2]" in level_line
    assert "Defaults to 2." not in level_line


def test_standard_layout_does_not_duplicate_existing_bracket_default_block() -> None:
    def demo(*, level: int = 2) -> None:
        """Set output level [default: 2]."""
        return None

    parser = Interfacy(backend="argparse", help_layout=StandardLayout(), print_result=False)
    parser.add_command(demo)
    help_text = parser.build_parser().format_help()
    level_line = next(line for line in help_text.splitlines() if "--level" in line)

    assert level_line.count("[default: 2]") == 1


def test_argparse_layout_root_usage_includes_subcommand_choices() -> None:
    def dense_parameters() -> None:
        """Exercise choices, defaults, tuples, and long descriptions."""

    def path_ops() -> None:
        """Mix positionals, varargs, and keyword-only options."""

    parser = Interfacy(backend="argparse", help_layout=ArgparseLayout(), print_result=False)
    parser.add_command(dense_parameters)
    parser.add_command(path_ops)

    help_text = parser.build_parser().format_help()
    assert "{dense-parameters,path-ops}" in help_text


def test_argparse_layout_uses_primary_boolean_option_form() -> None:
    def run(flag: bool = False) -> None:
        """No-op."""

    parser = Interfacy(backend="argparse", help_layout=ArgparseLayout(), print_result=False)
    parser.add_command(run)

    help_text = parser.build_parser().format_help()
    assert "--flag" in help_text
    assert "--no-flag" not in help_text


def test_argparse_layout_usage_uses_single_primary_boolean_form() -> None:
    def run(*, dry_run: bool = False) -> None:
        """No-op."""

    parser = Interfacy(backend="argparse", help_layout=ArgparseLayout(), print_result=False)
    parser.add_command(run)

    help_text = parser.build_parser().format_help()
    assert "[--dry-run]" in help_text
    assert "| --dry-run" not in help_text


def test_argparse_layout_shows_subcommand_description_rows() -> None:
    def run_fast() -> None:
        """Fast mode."""

    def run_safe() -> None:
        """Safe mode."""

    parser = Interfacy(backend="argparse", help_layout=ArgparseLayout(), print_result=False)
    parser.add_command(run_fast)
    parser.add_command(run_safe)

    help_text = parser.build_parser().format_help()
    assert "run-fast" in help_text
    assert "Fast mode." in help_text
    assert "run-safe" in help_text
    assert "Safe mode." in help_text


def test_argparse_layout_root_uses_commands_section_without_choices_header_line() -> None:
    def dense_parameters() -> None:
        """Dense command."""

    def path_ops() -> None:
        """Path command."""

    parser = Interfacy(backend="argparse", help_layout=ArgparseLayout(), print_result=False)
    parser.add_command(dense_parameters)
    parser.add_command(path_ops)

    help_text = parser.build_parser().format_help()
    assert "commands:" in help_text
    assert "positional arguments:" not in help_text
    assert "\ncommands:\n  {dense-parameters,path-ops}" not in help_text
    assert re.search(r"^\s*dense-parameters\s+Dense command\.$", help_text, re.MULTILINE)
    assert re.search(r"^\s*path-ops\s+Path command\.$", help_text, re.MULTILINE)


def test_argparser_help_position_kwarg_overrides_layout_help_position() -> None:
    parser = Interfacy(
        backend="argparse",
        help_layout=StandardLayout(help_position=24),
        help_position=42,
        executable_flags=[
            ExecutableFlag(
                ("-d", "--disable-job-duration-limit"),
                lambda: None,
                help="Disable the per-job duration limit.",
            )
        ],
        print_result=False,
    )

    def serve() -> None:
        """Run the service."""

    parser.add_command(serve)
    help_text = parser.build_parser().format_help()

    assert re.search(
        r"^\s*-d, --disable-job-duration-limit\s+Disable the per-job duration limit\.$",
        help_text,
        re.MULTILINE,
    )


def test_interfacy_layout_usage_lists_concrete_subcommand_choices() -> None:
    class Math:
        def add(self) -> None:
            return None

        def mul(self) -> None:
            return None

    parser = Interfacy(backend="argparse", help_layout=InterfacyLayout(), print_result=False)
    parser.add_command(Math)

    help_text = parser.build_parser().format_help()
    assert "{add,mul}" in help_text


def test_standard_layout_class_root_help_renders_one_commands_section() -> None:
    class Calculator:
        def add(self, a: float, b: float) -> float:
            return a + b

        def mul(self, a: float, b: float) -> float:
            return a * b

    parser = Interfacy(backend="argparse", help_layout=StandardLayout(), print_result=False)
    parser.add_command(Calculator)

    help_text = parser.build_parser().format_help()

    assert len(re.findall(r"^commands:$", help_text, re.MULTILINE)) == 1
    assert len(re.findall(r"^\s+add(?:\s|$)", help_text, re.MULTILINE)) == 1
    assert len(re.findall(r"^\s+mul(?:\s|$)", help_text, re.MULTILINE)) == 1


def test_interfacy_layout_help_and_choices_metadata_align_in_same_column() -> None:
    def dense_parameters(
        input_path: str,
        output_path: str,
        *,
        mode: Literal["fast", "safe", "balanced"] = "balanced",
    ) -> None:
        return None

    parser = Interfacy(backend="argparse", help_layout=InterfacyLayout(), print_result=False)
    parser.add_command(dense_parameters)

    help_text = parser.build_parser().format_help()
    help_line = next(
        line for line in help_text.splitlines() if "--help" in line and "Show " in line
    )
    mode_line = next(
        line for line in help_text.splitlines() if "--mode" in line and "[choices:" in line
    )
    assert help_line.index("Show") == mode_line.index("[choices:")


def test_interfacy_layout_help_and_type_metadata_align_in_same_column() -> None:
    def path_ops(source: str, target: str, *extras: str, level: int = 2) -> None:
        return None

    parser = Interfacy(backend="argparse", help_layout=InterfacyLayout(), print_result=False)
    parser.add_command(path_ops)

    help_text = parser.build_parser().format_help()
    help_line = next(
        line for line in help_text.splitlines() if "--help" in line and "Show " in line
    )
    level_line = next(
        line for line in help_text.splitlines() if "--level" in line and "[default=" in line
    )
    assert help_line.index("Show") == level_line.index("[default=")


def test_interfacy_layout_displays_empty_string_defaults_explicitly() -> None:
    def db_tool(*, db_path: str = "") -> None:
        """SQLite database path. Use the configured default when empty."""
        return None

    parser = Interfacy(backend="argparse", help_layout=InterfacyLayout(), print_result=False)
    parser.add_command(db_tool)

    help_text = re.sub(r"\x1b\[[0-9;]*m", "", parser.build_parser().format_help())
    db_line = next(
        line for line in help_text.splitlines() if "--db-path" in line and "[default=" in line
    )

    assert '[default="", type: str]' in db_line


def test_aligned_layout_help_only_option_row_is_not_over_indented() -> None:
    def dense_parameters() -> None:
        """Dense command."""

    def path_ops() -> None:
        """Path command."""

    parser = Interfacy(backend="argparse", help_layout=Aligned(), print_result=False)
    parser.add_command(dense_parameters)
    parser.add_command(path_ops)

    help_text = parser.build_parser().format_help()
    help_line = next(
        line for line in help_text.splitlines() if "--help" in line and "Show " in line
    )
    assert help_line.startswith("  --help")
    assert not help_line.startswith("        --help")


def test_aligned_typed_positional_literal_choices_keep_column_padding() -> None:
    def demo(target: Literal["dev", "prod"]) -> None:
        return None

    parser = Interfacy(backend="argparse", help_layout=AlignedTyped(), print_result=False)
    parser.add_command(demo)
    help_text = re.sub(r"\x1b\[[0-9;]*m", "", parser.build_parser().format_help())
    target_line = next(
        line for line in help_text.splitlines() if "TARGET" in line and "[choices:" in line
    )

    assert "TARGET [choices:" not in target_line
    assert "TARGET                   [choices: dev, prod]" in target_line


def test_aligned_typed_help_aligns_to_metadata_column_when_options_are_metadata_only() -> None:
    def ytmp3_like(
        *urls: str,
        album: str | None = None,
        output: str = "%(title)s.%(ext)s",
        quiet: bool = False,
    ) -> None:
        return None

    parser = Interfacy(backend="argparse", help_layout=AlignedTyped(), print_result=False)
    parser.add_command(ytmp3_like)
    help_text = re.sub(r"\x1b\[[0-9;]*m", "", parser.build_parser().format_help())

    lines = help_text.splitlines()
    help_line = next(
        line for line in lines if "--help" in line and "Show this help message and exit" in line
    )
    album_line = next(line for line in lines if "--album" in line and "[type:" in line)
    output_line = next(
        line for line in lines if "--output" in line and "[%(title)s.%(ext)s]" in line
    )

    help_idx = help_line.index("Show this help message and exit")
    assert help_idx == album_line.index("[type:")
    assert help_idx == output_line.index("[")


def test_usage_metavars_use_kebab_case_for_nested_class_commands() -> None:
    class ReportTool:
        def __init__(self, output_dir: str) -> None:
            self.output_dir = output_dir

        def compare(self, left: str, right: str) -> None:
            return None

    parser = Interfacy(backend="argparse", help_layout=InterfacyLayout(), print_result=False)
    parser.add_command(ReportTool)
    root = parser.build_parser()
    action = next(a for a in root._actions if isinstance(a, argparse._SubParsersAction))
    compare_parser = action.choices["compare"]
    help_text = compare_parser.format_help()

    assert "OUTPUT-DIR" in help_text
    assert "OUTPUT_DIR" not in help_text

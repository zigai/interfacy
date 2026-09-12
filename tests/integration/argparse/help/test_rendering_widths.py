from __future__ import annotations

import argparse
import os
import re
import shutil
from typing import Literal

import pytest

from interfacy import CommandGroup, Interfacy
from interfacy.help.presets import (
    Aligned,
    AlignedTyped,
    ArgparseLayout,
    ClapLayout,
    InterfacyLayout,
    Modern,
    StandardLayout,
)
from interfacy.help.wrapping import expand_usage_parts
from interfacy.naming import DefaultFlagStrategy


@pytest.fixture
def fixed_terminal_width(monkeypatch: pytest.MonkeyPatch) -> None:
    size = os.terminal_size((80, 24))
    monkeypatch.setattr(os, "get_terminal_size", lambda *args, **kwargs: size)
    monkeypatch.setattr(shutil, "get_terminal_size", lambda *args, **kwargs: size)
    monkeypatch.setenv("COLUMNS", "80")


@pytest.mark.parametrize(
    ("layout", "expected_positional_choices", "expected_flag_choices"),
    [
        (
            StandardLayout(),
            "[choices: alpha, beta]",
            "[choices: csv, txt]",
        ),
        (
            ArgparseLayout(),
            "Choices: alpha, beta.",
            "Choices: csv, txt.",
        ),
        (
            InterfacyLayout(),
            "[choices: alpha, beta]",
            "[choices: csv, txt, default=csv]",
        ),
        (
            Modern(),
            "choices: alpha, beta",
            "choices: csv, txt",
        ),
        (
            Aligned(),
            "[choices: alpha, beta]",
            "[choices: csv, txt]",
        ),
        (
            AlignedTyped(),
            "[choices: alpha, beta]",
            "[choices: csv, txt]",
        ),
        (
            ClapLayout(),
            "[possible values: alpha, beta]",
            "[possible values: csv, txt]",
        ),
    ],
)
def test_all_layouts_render_literal_choices_for_positional_and_optional_flag(
    layout,
    expected_positional_choices: str,
    expected_flag_choices: str,
) -> None:
    def demo(subject: Literal["alpha", "beta"], *, output: Literal["csv", "txt"] = "csv") -> None:
        """Demo command."""

    parser = Interfacy(backend="argparse", help_layout=layout, print_result=False)
    parser.add_command(demo)

    help_text = parser.build_parser().format_help()
    assert expected_positional_choices in help_text
    assert expected_flag_choices in help_text


@pytest.mark.parametrize(
    ("layout", "expected_required_flag_choices"),
    [
        (StandardLayout(), "[choices: left, right]"),
        (ArgparseLayout(), "Choices: left, right."),
        (InterfacyLayout(), "[choices: left, right]"),
        (Modern(), "choices: left, right"),
        (Aligned(), "[choices: left, right]"),
        (AlignedTyped(), "[choices: left, right]"),
        (ClapLayout(), "[possible values: left, right]"),
    ],
)
def test_all_layouts_render_literal_choices_for_required_flags(
    layout,
    expected_required_flag_choices: str,
) -> None:
    def demo(*, axis: Literal["left", "right"], output: Literal["csv", "txt"] = "csv") -> None:
        """Demo command."""

    parser = Interfacy(
        backend="argparse",
        help_layout=layout,
        print_result=False,
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
    )
    parser.add_command(demo)

    help_text = parser.build_parser().format_help()
    assert expected_required_flag_choices in help_text


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("{alpha,beta,gamma}", ["{alpha,", "beta,", "gamma}"]),
        ("[{alpha,beta,gamma}]", ["[{alpha,", "beta,", "gamma}]"]),
        ("{single}", ["{single}"]),
        ("{}", ["{}"]),
        ("intrinsically-overlong-atom", ["intrinsically-overlong-atom"]),
    ],
)
def test_expand_usage_parts_preserves_choice_atoms(token: str, expected: list[str]) -> None:
    assert expand_usage_parts([token], available_width=10) == expected


def test_argparse_layout_wraps_overwide_command_choices_without_token_loss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    size = os.terminal_size((35, 24))
    monkeypatch.setattr(os, "get_terminal_size", lambda *args, **kwargs: size)
    monkeypatch.setattr(shutil, "get_terminal_size", lambda *args, **kwargs: size)

    parser = Interfacy(backend="argparse", help_layout=ArgparseLayout())
    for name in ("alpha-long-command", "beta-long-command", "gamma-long-command"):
        parser.add_command(lambda: None, name=name)

    help_text = parser.build_parser().format_help()
    usage = help_text[: help_text.index("\n\n")]

    assert "alpha-long-command," in usage
    assert "\n       beta-long-command," in usage
    assert "\n       gamma-long-command}" in usage
    assert usage.index("alpha-long-command") < usage.index("beta-long-command")
    assert usage.index("beta-long-command") < usage.index("gamma-long-command")


def test_argparse_layout_keeps_intrinsically_overlong_command_atom(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    size = os.terminal_size((24, 24))
    monkeypatch.setattr(os, "get_terminal_size", lambda *args, **kwargs: size)
    monkeypatch.setattr(shutil, "get_terminal_size", lambda *args, **kwargs: size)
    name = "one-command-name-wider-than-the-terminal"
    parser = Interfacy(backend="argparse", help_layout=ArgparseLayout())
    parser.add_command(lambda: None, name=name)
    parser.add_command(lambda: None, name="short")

    help_text = parser.build_parser().format_help()

    assert name in help_text[: help_text.index("\n\n")]


@pytest.mark.usefixtures("fixed_terminal_width")
def test_clap_layout_wraps_long_possible_values() -> None:
    def list_items(
        sort: Literal[
            "name",
            "loc",
            "ruff_rate",
            "mypy_rate",
            "pylint_rate",
            "pylint_score",
        ] = "name",
    ) -> None:
        return None

    parser = Interfacy(backend="argparse", help_layout=ClapLayout(), print_result=False)
    parser.add_command(list_items)

    help_text = parser.build_parser().format_help()
    assert "[possible values:" in help_text
    assert "possible values: name, loc,\n" in help_text


def test_clap_layout_single_command_description_precedes_usage() -> None:
    def command_one() -> None:
        """Project command suite."""
        return None

    parser = Interfacy(backend="argparse", help_layout=ClapLayout(), print_result=False)
    parser.add_command(command_one)

    help_text = parser.build_parser().format_help()
    description_idx = help_text.index("Project command suite.")
    usage_idx = help_text.index("Usage:")
    assert description_idx < usage_idx


def test_clap_layout_root_description_precedes_usage() -> None:
    def command_one() -> None:
        """First command."""
        return None

    def command_two() -> None:
        """Second command."""
        return None

    parser = Interfacy(
        backend="argparse",
        description="Project command suite.",
        help_layout=ClapLayout(),
        print_result=False,
    )
    parser.add_command(command_one)
    parser.add_command(command_two)

    help_text = parser.build_parser().format_help()
    description_idx = help_text.index("Project command suite.")
    usage_idx = help_text.index("Usage:")
    assert description_idx < usage_idx


def test_clap_layout_styles_group_and_command_rows_consistently(monkeypatch) -> None:
    ops = CommandGroup("ops")
    nested = CommandGroup(
        "nested-tools",
        description="Nested subgroup with a longer name to test alignment.",
        aliases=("nested",),
    )
    ops.add_group(nested)
    ops.add_command(
        lambda: None,
        name="cache_prune",
        aliases=("prune",),
        description="Prune cache keys; bool default True should show --no-dry-run.",
    )

    layout = ClapLayout()
    parser = Interfacy(backend="argparse", help_layout=layout, print_result=False)
    parser.add_command(ops)
    schema = parser.build_parser_schema()
    ops_schema = schema.get_command("ops")
    assert ops_schema.subcommands is not None

    monkeypatch.setattr("interfacy.help.presets.with_style", lambda text, style: f"<S>{text}</S>")
    help_text = layout.get_help_for_multiple_commands(ops_schema.subcommands)

    assert "   <S>nested-tools, nested</S>" in help_text
    assert "   <S>cache-prune, prune</S>" in help_text


@pytest.mark.usefixtures("fixed_terminal_width")
def test_clap_layout_wrapped_description_continuation_aligns() -> None:
    def compress_videos(
        directory: str,
        *,
        crf: int = 21,
    ) -> None:
        """Compress all video files in directory."""
        return None

    # Force a long option description to wrap across lines.
    compress_videos.__annotations__["crf"] = int
    compress_videos.__doc__ = (
        "Compress all video files in directory.\n\n"
        "Args:\n"
        "    directory: Target directory.\n"
        "    crf: Constant Rate Factor for compression Lorem ipsum dolor sit amet, "
        "consectetur adipiscing elit. Morbi vel libero et turpis bibendum fringilla."
    )

    parser = Interfacy(backend="argparse", help_layout=ClapLayout(), print_result=False)
    parser.add_command(compress_videos)
    help_text = parser.build_parser().format_help()

    lines = help_text.splitlines()
    first = next(line for line in lines if "--crf <CRF>" in line)
    first_idx = first.index("Constant")
    second = next(line for line in lines if "ipsum dolor sit amet" in line)
    second_idx = second.index("ipsum")
    assert first_idx == second_idx


def test_clap_layout_group_defaults_align_in_same_column() -> None:
    class GroupArgs:
        def __init__(
            self,
            workspace: str,
            *,
            region: str = "us-east-1",
            retries: int = 2,
            debug: bool = False,
        ) -> None:
            return None

    ops = CommandGroup("ops").with_args(GroupArgs)
    ops.add_command(lambda: None, name="cache_prune")

    parser = Interfacy(backend="argparse", help_layout=ClapLayout(), print_result=False)
    parser.add_command(ops)
    root = parser.build_parser()
    action = next(a for a in root._actions if isinstance(a, argparse._SubParsersAction))
    ops_parser = action.choices["ops"]
    help_text = ops_parser.format_help()

    region_line = next(line for line in help_text.splitlines() if "--region <REGION>" in line)
    retries_line = next(line for line in help_text.splitlines() if "--retries <RETRIES>" in line)
    assert region_line.index("[default:") == retries_line.index("[default:")


@pytest.mark.parametrize(
    "layout",
    [
        StandardLayout(),
        ArgparseLayout(),
        InterfacyLayout(),
        Modern(),
        Aligned(),
        AlignedTyped(),
        ClapLayout(),
    ],
)
def test_layout_class_initializer_uses_class_arg_descriptions(layout) -> None:
    class Project:
        """Project command suite.

        Args:
            workspace: Workspace directory.
            retries: Number of retries.
        """

        def __init__(self, workspace: str, *, retries: int = 2) -> None:
            self.workspace = workspace
            self.retries = retries

        def sync(self) -> None:
            """Sync the project."""
            return None

    parser = Interfacy(backend="argparse", help_layout=layout, print_result=False)
    parser.add_command(Project)

    help_text = parser.build_parser().format_help()

    assert "Workspace directory." in help_text
    assert "Number of retries" in help_text


@pytest.mark.parametrize(
    "layout_cls",
    [
        InterfacyLayout,
        Aligned,
        AlignedTyped,
        Modern,
        StandardLayout,
        ArgparseLayout,
        ClapLayout,
    ],
)
def test_layout_command_descriptions_wrap_to_terminal_width(layout_cls, monkeypatch) -> None:
    monkeypatch.setattr(
        "shutil.get_terminal_size",
        lambda *args, **kwargs: os.terminal_size((80, 24)),
    )
    monkeypatch.setattr(
        "os.get_terminal_size",
        lambda *args, **kwargs: os.terminal_size((80, 24)),
    )

    def sync() -> None:
        """Synchronize X bookmarks and likes into the archive and return a sync summary string."""

    def export() -> None:
        """Export archived records to a JSON or JSONL file and return an export summary string."""

    parser = Interfacy(backend="argparse", help_layout=layout_cls(), print_result=False)
    parser.add_command(sync)
    parser.add_command(export)

    help_text = re.sub(r"\x1b\[[0-9;]*m", "", parser.build_parser().format_help())

    command_lines = [
        line
        for line in help_text.splitlines()
        if "Synchronize X bookmarks" in line or "return a sync summary string" in line
    ]
    assert len(command_lines) >= 2
    assert all(len(line) <= 80 for line in help_text.splitlines())


def test_schema_multi_command_usage_wraps_long_windows_prog(monkeypatch) -> None:
    monkeypatch.setattr(
        "shutil.get_terminal_size",
        lambda *args, **kwargs: os.terminal_size((80, 24)),
    )
    monkeypatch.setattr(
        "os.get_terminal_size",
        lambda *args, **kwargs: os.terminal_size((80, 24)),
    )

    def sync() -> None:
        """Synchronize X bookmarks."""

    def export() -> None:
        """Export archived records."""

    parser = Interfacy(backend="argparse", help_layout=InterfacyLayout(), print_result=False)
    parser.add_command(sync)
    parser.add_command(export)
    built_parser = parser.build_parser()
    built_parser.prog = r"D:\a\interfacy\interfacy\.venv\Scripts\pytest.exe"

    help_text = re.sub(r"\x1b\[[0-9;]*m", "", built_parser.format_help())

    assert all(len(line) <= 80 for line in help_text.splitlines())


def test_template_schema_descriptions_wrap_to_terminal_width(monkeypatch) -> None:
    monkeypatch.setattr(
        "shutil.get_terminal_size",
        lambda *args, **kwargs: os.terminal_size((40, 24)),
    )
    monkeypatch.setattr(
        "os.get_terminal_size",
        lambda *args, **kwargs: os.terminal_size((40, 24)),
    )

    def probe() -> None:
        """Probe CLI for finding help rendering defects across layouts and backends."""

    parser = Interfacy(backend="argparse", help_layout=InterfacyLayout(), print_result=False)
    parser.add_command(probe)
    built_parser = parser.build_parser()
    built_parser.prog = "probe"
    help_text = re.sub(r"\x1b\[[0-9;]*m", "", built_parser.format_help())

    assert "Probe CLI for finding help rendering\ndefects across layouts and backends." in help_text
    assert all(len(line) <= 40 for line in help_text.splitlines())


def test_template_usage_wrapping_preserves_command_choice_tokens(monkeypatch) -> None:
    monkeypatch.setattr(
        "shutil.get_terminal_size",
        lambda *args, **kwargs: os.terminal_size((50, 24)),
    )
    monkeypatch.setattr(
        "os.get_terminal_size",
        lambda *args, **kwargs: os.terminal_size((50, 24)),
    )

    def command_with_a_really_really_long_name() -> None:
        return None

    def short() -> None:
        return None

    parser = Interfacy(backend="argparse", help_layout=InterfacyLayout(), print_result=False)
    parser.add_command(command_with_a_really_really_long_name)
    parser.add_command(short)
    help_text = re.sub(r"\x1b\[[0-9;]*m", "", parser.build_parser().format_help())

    broken_token = "rea" + "ll\ny"
    assert broken_token not in help_text
    assert "command-with-a-really-really-long-name" in help_text


def test_long_command_name_does_not_force_one_character_description_wrapping(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "shutil.get_terminal_size",
        lambda *args, **kwargs: os.terminal_size((60, 24)),
    )
    monkeypatch.setattr(
        "os.get_terminal_size",
        lambda *args, **kwargs: os.terminal_size((60, 24)),
    )

    def command_with_a_really_really_long_name() -> None:
        """Long command row description remains readable."""

    def short() -> None:
        """Short command."""

    parser = Interfacy(backend="argparse", help_layout=StandardLayout(), print_result=False)
    parser.add_command(command_with_a_really_really_long_name)
    parser.add_command(short)
    help_text = parser.build_parser().format_help()

    assert "\n                                                       L\n" not in help_text
    assert "Long command row" in help_text
    assert "description" in help_text
    assert "remains" in help_text
    assert "readable." in help_text


def test_aligned_layout_wraps_default_rows_after_metadata(monkeypatch) -> None:
    monkeypatch.setattr(
        "shutil.get_terminal_size",
        lambda *args, **kwargs: os.terminal_size((100, 24)),
    )
    monkeypatch.setattr(
        "os.get_terminal_size",
        lambda *args, **kwargs: os.terminal_size((100, 24)),
    )

    def cache(
        *,
        cache_dir: str = "get_default_cache_dir()",
    ) -> None:
        """List cache entries.

        Args:
            cache_dir: Directory containing the whispers cache. Defaults to the value of the
                WHISPERS_CACHE_DIR environment variable if set.
        """

    parser = Interfacy(backend="argparse", help_layout=Aligned(), print_result=False)
    parser.add_command(cache)

    help_text = re.sub(r"\x1b\[[0-9;]*m", "", parser.build_parser().format_help())

    assert all(len(line) <= 100 for line in help_text.splitlines())
    assert "WHISPERS_CACHE_DIR" in help_text


def test_clap_layout_defaults_align_when_option_label_exceeds_base_width() -> None:
    def keyword_only_options(
        *,
        region: str = "us-east-1",
        timeout_s: float = 1.5,
    ) -> None:
        return None

    parser = Interfacy(backend="argparse", help_layout=ClapLayout(), print_result=False)
    parser.add_command(keyword_only_options)

    help_text = parser.build_parser().format_help()
    region_line = next(line for line in help_text.splitlines() if "--region <REGION>" in line)
    timeout_line = next(
        line for line in help_text.splitlines() if "--timeout-s <TIMEOUT-S>" in line
    )
    assert region_line.index("[default:") == timeout_line.index("[default:")


def test_ansi_styled_legacy_epilog_is_not_duplicated_for_subcommands() -> None:
    class StyledTitleClapLayout(ClapLayout):
        def _format_commands_title(self) -> str:
            return "\x1b[32mCommands:\x1b[0m"

    ops = CommandGroup("ops")
    ops.add_command(lambda: None, name="cache_prune")

    parser = Interfacy(backend="argparse", help_layout=StyledTitleClapLayout(), print_result=False)
    parser.add_command(ops)
    root = parser.build_parser()
    action = next(a for a in root._actions if isinstance(a, argparse._SubParsersAction))
    ops_parser = action.choices["ops"]
    help_text = re.sub(r"\x1b\[[0-9;]*m", "", ops_parser.format_help())

    assert help_text.count("Commands:") == 1


@pytest.mark.parametrize("layout_cls", [Aligned, AlignedTyped])
def test_aligned_family_long_option_rows_keep_separator_before_default_slot(
    layout_cls: type[Aligned | AlignedTyped],
) -> None:
    def sniffa_like(
        *,
        webdriver_endpoint: str = "http://127.0.0.1:4444",
        bidi_session_timeout_seconds: int = 30,
        include_intermediate: bool = False,
        writer_queue_size: int = 10000,
    ) -> None:
        return None

    parser = Interfacy(backend="argparse", help_layout=layout_cls(), print_result=False)
    parser.add_command(sniffa_like)
    help_text = re.sub(r"\x1b\[[0-9;]*m", "", parser.build_parser().format_help())

    lines = help_text.splitlines()
    for long_flag in (
        "--webdriver-endpoint",
        "--bidi-session-timeout-seconds",
        "--include-intermediate",
        "--writer-queue-size",
    ):
        line = next(line for line in lines if long_flag in line)
        assert f"{long_flag}[" not in line


def test_argparse_layout_does_not_duplicate_existing_default_sentence() -> None:
    def c2p(*, no_tokens: bool = True) -> None:
        """Convert source to a prompt.

        Args:
            no_tokens: Include token information in the output. Defaults to True.
        """
        return None

    parser = Interfacy(backend="argparse", help_layout=ArgparseLayout(), print_result=False)
    parser.add_command(c2p)
    help_text = parser.build_parser().format_help()
    normalized_help = " ".join(help_text.split())

    assert "Defaults to True.. Defaults to True." not in normalized_help
    assert normalized_help.count("Defaults to True.") == 1


def test_argparse_layout_collapses_terminal_double_period_before_default_sentence() -> None:
    def sniffa(*, backend: str = "cdp") -> None:
        """Sniffa demo.

        Args:
            backend: Browser protocol backend. Use cdp for Chromium and bidi for Firefox..
        """
        return None

    parser = Interfacy(backend="argparse", help_layout=ArgparseLayout(), print_result=False)
    parser.add_command(sniffa)
    help_text = parser.build_parser().format_help()

    assert "Firefox.. Defaults to cdp." not in help_text
    assert "Firefox. Defaults to cdp." in help_text


def test_argparse_layout_dot_default_uses_single_terminal_period() -> None:
    def open_file_explorer(*, directory: str = ".") -> None:
        """Open the platform file explorer at a given path."""
        return None

    parser = Interfacy(backend="argparse", help_layout=ArgparseLayout(), print_result=False)
    parser.add_command(open_file_explorer)
    help_text = parser.build_parser().format_help()

    assert "Defaults to .." not in help_text
    assert "Defaults to ." in help_text


def test_argparse_layout_renders_percent_defaults_without_keyerror(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def ytmp3(*, output: str = "%(title)s.%(ext)s") -> None:
        """Download content."""
        return None

    parser = Interfacy(backend="argparse", help_layout=ArgparseLayout(), print_result=False)
    parser.add_command(ytmp3)

    try:
        parser.invoke(args=["--help"])
    except SystemExit:
        pass

    out = capsys.readouterr()
    help_text = out.out + out.err
    assert "%(title)s.%(ext)s" in help_text

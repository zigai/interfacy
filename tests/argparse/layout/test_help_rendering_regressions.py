from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from typing import Literal

import pytest

from interfacy import CommandGroup
from interfacy.appearance.layouts import (
    Aligned,
    AlignedTyped,
    ArgparseLayout,
    ClapLayout,
    InterfacyLayout,
)
from interfacy.argparse_backend import Argparser
from interfacy.argparse_backend.argument_parser import ArgumentParser


@dataclass
class ExpandableSettings:
    enabled: bool = False


DEFAULT_EXPANDABLE_SETTINGS = ExpandableSettings()


def run_with_expandable_settings(
    settings: ExpandableSettings = DEFAULT_EXPANDABLE_SETTINGS,
) -> None:
    return None


def test_argparse_layout_root_usage_includes_subcommand_choices() -> None:
    def dense_parameters() -> None:
        """Exercise choices, defaults, tuples, and long descriptions."""

    def path_ops() -> None:
        """Mix positionals, varargs, and keyword-only options."""

    parser = Argparser(help_layout=ArgparseLayout(), sys_exit_enabled=False, print_result=False)
    parser.add_command(dense_parameters)
    parser.add_command(path_ops)

    help_text = parser.build_parser().format_help()
    assert "{dense-parameters,path-ops}" in help_text


def test_argparse_layout_uses_primary_boolean_option_form() -> None:
    def run(flag: bool = False) -> None:
        """No-op."""

    parser = Argparser(help_layout=ArgparseLayout(), sys_exit_enabled=False, print_result=False)
    parser.add_command(run)

    help_text = parser.build_parser().format_help()
    assert "--flag" in help_text
    assert "--no-flag" not in help_text


def test_argparse_layout_usage_uses_single_primary_boolean_form() -> None:
    def run(*, dry_run: bool = False) -> None:
        """No-op."""

    parser = Argparser(help_layout=ArgparseLayout(), sys_exit_enabled=False, print_result=False)
    parser.add_command(run)

    help_text = parser.build_parser().format_help()
    assert "[--dry-run]" in help_text
    assert "| --dry-run" not in help_text


def test_argparse_layout_shows_subcommand_description_rows() -> None:
    def run_fast() -> None:
        """Fast mode."""

    def run_safe() -> None:
        """Safe mode."""

    parser = Argparser(help_layout=ArgparseLayout(), sys_exit_enabled=False, print_result=False)
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

    parser = Argparser(help_layout=ArgparseLayout(), sys_exit_enabled=False, print_result=False)
    parser.add_command(dense_parameters)
    parser.add_command(path_ops)

    help_text = parser.build_parser().format_help()
    assert "commands:" in help_text
    assert "positional arguments:" not in help_text
    assert "\ncommands:\n  {dense-parameters,path-ops}" not in help_text
    assert re.search(r"^\s*dense-parameters\s+Dense command\.$", help_text, re.MULTILINE)
    assert re.search(r"^\s*path-ops\s+Path command\.$", help_text, re.MULTILINE)


def test_nested_manual_parser_uses_leaf_metavar_for_append_action() -> None:
    parser = ArgumentParser(prog="manual")
    subparsers = parser.add_subparsers(dest="command", required=True)
    deploy = subparsers.add_parser("deploy")
    deploy.add_argument("--tag", action="append", default=None, help="Attach a tag.")

    help_text = deploy.format_help()
    assert "--tag TAG" in help_text
    assert "DEPLOY__TAG" not in help_text


def test_group_function_commands_render_kebab_case_names() -> None:
    ops = CommandGroup("ops")

    def cache_prune() -> None:
        """Prune cache keys."""

    ops.add_command(cache_prune)
    parser = Argparser(help_layout=ArgparseLayout(), sys_exit_enabled=False, print_result=False)
    parser.add_command(ops)

    root = parser.build_parser()
    action = next(a for a in root._actions if isinstance(a, argparse._SubParsersAction))
    ops_parser = action.choices["ops"]
    help_text = ops_parser.format_help()

    assert "cache-prune" in help_text
    assert "cache_prune" not in help_text


def test_interfacy_layout_usage_lists_concrete_subcommand_choices() -> None:
    class Math:
        def add(self) -> None:
            return None

        def mul(self) -> None:
            return None

    parser = Argparser(help_layout=InterfacyLayout(), sys_exit_enabled=False, print_result=False)
    parser.add_command(Math)

    help_text = parser.build_parser().format_help()
    assert "{add,mul}" in help_text


def test_interfacy_layout_usage_subcommand_choices_exclude_aliases() -> None:
    ops = CommandGroup("ops")
    ops.add_command(lambda: None, name="cache_prune", aliases=("prune",))

    parser = Argparser(help_layout=InterfacyLayout(), sys_exit_enabled=False, print_result=False)
    parser.add_command(ops)

    root = parser.build_parser()
    action = next(a for a in root._actions if isinstance(a, argparse._SubParsersAction))
    ops_parser = action.choices["ops"]
    help_text = ops_parser.format_help()

    assert "{cache-prune}" in help_text
    assert "{cache-prune,prune}" not in help_text


def test_interfacy_layout_help_and_choices_metadata_align_in_same_column() -> None:
    def dense_parameters(
        input_path: str,
        output_path: str,
        *,
        mode: Literal["fast", "safe", "balanced"] = "balanced",
    ) -> None:
        return None

    parser = Argparser(help_layout=InterfacyLayout(), sys_exit_enabled=False, print_result=False)
    parser.add_command(dense_parameters)

    help_text = parser.build_parser().format_help()
    help_line = next(
        line for line in help_text.splitlines() if "--help" in line and "show " in line
    )
    mode_line = next(
        line for line in help_text.splitlines() if "--mode" in line and "[choices:" in line
    )
    assert help_line.index("show") == mode_line.index("[choices:")


def test_interfacy_layout_help_and_type_metadata_align_in_same_column() -> None:
    def path_ops(source: str, target: str, *extras: str, level: int = 2) -> None:
        return None

    parser = Argparser(help_layout=InterfacyLayout(), sys_exit_enabled=False, print_result=False)
    parser.add_command(path_ops)

    help_text = parser.build_parser().format_help()
    help_line = next(
        line for line in help_text.splitlines() if "--help" in line and "show " in line
    )
    level_line = next(
        line for line in help_text.splitlines() if "--level" in line and "[type:" in line
    )
    assert help_line.index("show") == level_line.index("[type:")


def test_interfacy_layout_does_not_add_extra_leading_space_for_ansi_only_description() -> None:
    layout = InterfacyLayout()
    values = {
        "description": "\x1b[38;5;15m\x1b[0m",
        "extra": "[type: int, default=3]",
    }
    applied = layout._apply_interfacy_columns(values)
    assert applied["extra"] == "[type: int, default=3]"


def test_aligned_layout_help_only_option_row_is_not_over_indented() -> None:
    def dense_parameters() -> None:
        """Dense command."""

    def path_ops() -> None:
        """Path command."""

    parser = Argparser(help_layout=Aligned(), sys_exit_enabled=False, print_result=False)
    parser.add_command(dense_parameters)
    parser.add_command(path_ops)

    help_text = parser.build_parser().format_help()
    help_line = next(
        line for line in help_text.splitlines() if "--help" in line and "show " in line
    )
    assert help_line.startswith("  --help")
    assert not help_line.startswith("        --help")


@pytest.mark.parametrize("layout_cls", [Aligned, AlignedTyped])
def test_aligned_family_omits_suppressed_boolean_default_for_model_expansion(
    layout_cls: type[Aligned | AlignedTyped],
) -> None:
    parser = Argparser(help_layout=layout_cls(), sys_exit_enabled=False, print_result=False)
    parser.add_command(run_with_expandable_settings)
    help_text = re.sub(r"\x1b\[[0-9;]*m", "", parser.build_parser().format_help())
    assert re.search(r"--settings[._-]?enabled", help_text)
    assert re.search(r"--settings[._-]?enabled\s+enabled", help_text)
    assert "true" not in help_text.lower()


def test_usage_metavars_use_kebab_case_for_nested_class_commands() -> None:
    class ReportTool:
        def __init__(self, output_dir: str) -> None:
            self.output_dir = output_dir

        def compare(self, left: str, right: str) -> None:
            return None

    parser = Argparser(help_layout=InterfacyLayout(), sys_exit_enabled=False, print_result=False)
    parser.add_command(ReportTool)
    root = parser.build_parser()
    action = next(a for a in root._actions if isinstance(a, argparse._SubParsersAction))
    compare_parser = action.choices["compare"]
    help_text = compare_parser.format_help()

    assert "OUTPUT-DIR" in help_text
    assert "OUTPUT_DIR" not in help_text


def test_argparse_layout_group_usage_includes_subcommand_choices() -> None:
    ops = CommandGroup("ops")
    ops.add_command(lambda: None, name="cache_prune")

    parser = Argparser(help_layout=ArgparseLayout(), sys_exit_enabled=False, print_result=False)
    parser.add_command(ops)
    root = parser.build_parser()
    action = next(a for a in root._actions if isinstance(a, argparse._SubParsersAction))
    ops_parser = action.choices["ops"]
    help_text = ops_parser.format_help()

    assert "{cache-prune}" in help_text


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

    parser = Argparser(help_layout=ClapLayout(), sys_exit_enabled=False, print_result=False)
    parser.add_command(list_items)

    help_text = parser.build_parser().format_help()
    assert "[possible values:" in help_text
    assert "possible values: name, loc,\n" in help_text


def test_clap_layout_single_command_description_precedes_usage() -> None:
    def command_one() -> None:
        """Project command suite."""
        return None

    parser = Argparser(help_layout=ClapLayout(), sys_exit_enabled=False, print_result=False)
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

    parser = Argparser(
        description="Project command suite.",
        help_layout=ClapLayout(),
        sys_exit_enabled=False,
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

    parser = Argparser(help_layout=ClapLayout(), sys_exit_enabled=False, print_result=False)
    parser.add_command(ops)
    schema = parser.build_parser_schema()
    ops_schema = schema.get_command("ops")
    assert ops_schema.subcommands is not None

    monkeypatch.setattr(
        "interfacy.appearance.layouts.with_style", lambda text, style: f"<S>{text}</S>"
    )
    help_text = parser.help_layout.get_help_for_multiple_commands(ops_schema.subcommands)

    assert "   <S>nested-tools, nested</S>" in help_text
    assert "   <S>cache-prune, prune</S>" in help_text


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

    parser = Argparser(help_layout=ClapLayout(), sys_exit_enabled=False, print_result=False)
    parser.add_command(compress_videos)
    help_text = parser.build_parser().format_help()

    lines = help_text.splitlines()
    first = next(line for line in lines if "--crf <CRF>" in line)
    first_idx = first.index("Constant")
    second = next(line for line in lines if "dolor sit amet, consectetur adipiscing elit." in line)
    second_idx = second.index("dolor")
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

    parser = Argparser(help_layout=ClapLayout(), sys_exit_enabled=False, print_result=False)
    parser.add_command(ops)
    root = parser.build_parser()
    action = next(a for a in root._actions if isinstance(a, argparse._SubParsersAction))
    ops_parser = action.choices["ops"]
    help_text = ops_parser.format_help()

    region_line = next(line for line in help_text.splitlines() if "--region <REGION>" in line)
    retries_line = next(line for line in help_text.splitlines() if "--retries <RETRIES>" in line)
    assert region_line.index("[default:") == retries_line.index("[default:")


def test_clap_layout_defaults_align_when_option_label_exceeds_base_width() -> None:
    def keyword_only_options(
        *,
        region: str = "us-east-1",
        timeout_s: float = 1.5,
    ) -> None:
        return None

    parser = Argparser(help_layout=ClapLayout(), sys_exit_enabled=False, print_result=False)
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

    parser = Argparser(
        help_layout=StyledTitleClapLayout(), sys_exit_enabled=False, print_result=False
    )
    parser.add_command(ops)
    root = parser.build_parser()
    action = next(a for a in root._actions if isinstance(a, argparse._SubParsersAction))
    ops_parser = action.choices["ops"]
    help_text = re.sub(r"\x1b\[[0-9;]*m", "", ops_parser.format_help())

    assert help_text.count("Commands:") == 1

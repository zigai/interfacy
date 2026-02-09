import argparse
import re
import textwrap
from collections.abc import Iterable
from typing import TYPE_CHECKING

from stdl.st import ansi_len, with_style

if TYPE_CHECKING:
    from interfacy.appearance.layout import HelpLayout

# Python 3.14 removed '_format_actions_usage', replaced with '_get_actions_usage_parts'
_HAS_FORMAT_ACTIONS_USAGE = hasattr(argparse.HelpFormatter, "_format_actions_usage")


class InterfacyHelpFormatter(argparse.HelpFormatter):
    """Help formatter that integrates Interfacy layout settings."""

    def _compat_format_actions_usage(
        self,
        actions: list[argparse.Action],
        groups: Iterable[argparse._MutuallyExclusiveGroup],
    ) -> str:
        """Compatibility wrapper for _format_actions_usage (removed in Python 3.14)."""
        if _HAS_FORMAT_ACTIONS_USAGE:
            return self._format_actions_usage(actions, groups)  # type: ignore[attr-defined]
        parts, _ = self._get_actions_usage_parts(actions, groups)  # type: ignore[attr-defined]
        return " ".join(parts)

    def set_help_layout(self, help_layout: "HelpLayout") -> None:
        """
        Attach a HelpLayout for formatting decisions.

        Args:
            help_layout (HelpLayout): Layout instance to use.
        """
        self._interfacy_help_layout = help_layout

    def _get_help_layout(self) -> "HelpLayout | None":
        return getattr(self, "_interfacy_help_layout", None)

    def start_section(self, heading: str | None) -> None:
        """
        Start a help section with optional layout styling.

        Args:
            heading (str | None): Section heading text.
        """
        layout = self._get_help_layout()
        if layout is not None and heading not in (None, argparse.SUPPRESS):
            title_map = getattr(layout, "section_title_map", None)
            heading_text = str(heading).strip()
            heading_key = heading_text.rstrip(":").strip().lower()
            if isinstance(title_map, dict):
                mapped = (
                    title_map.get(heading)
                    or title_map.get(heading_text)
                    or title_map.get(heading_key)
                )
                if mapped:
                    heading = mapped
            heading_style = getattr(layout, "section_heading_style", None)
            if heading_style is not None:
                try:
                    heading = with_style(str(heading), heading_style)
                except Exception:
                    pass
        return super().start_section(heading)

    def _split_lines(self, text: str, width: int) -> list[str]:
        return super()._split_lines(text, width)

    @staticmethod
    def _primary_boolean_option_strings(action: argparse.Action) -> list[str]:
        option_strings = list(action.option_strings)
        shorts = [s for s in option_strings if s.startswith("-") and not s.startswith("--")]
        longs = [s for s in option_strings if s.startswith("--")]
        if not longs:
            return option_strings

        base_flag = None
        no_flag = None
        for flag in longs:
            if flag.startswith("--no-"):
                no_flag = flag
            else:
                base_flag = flag

        if base_flag and not no_flag:
            no_flag = f"--no-{base_flag[2:]}"

        default_val = getattr(action, "default", False)
        primary_long = no_flag if bool(default_val) and no_flag else (base_flag or longs[0])

        normalized: list[str] = []
        if shorts:
            normalized.append(shorts[0])
        if primary_long and primary_long not in normalized:
            normalized.append(primary_long)
        return normalized or option_strings

    @staticmethod
    def _primary_boolean_usage_option_strings(action: argparse.Action) -> list[str]:
        normalized = InterfacyHelpFormatter._primary_boolean_option_strings(action)
        longs = [flag for flag in normalized if flag.startswith("--")]
        if longs:
            return [longs[0]]
        if normalized:
            return [normalized[0]]
        return list(action.option_strings)

    def _format_args(self, action: argparse.Action, default_metavar: str) -> str:
        result = super()._format_args(action, default_metavar)
        cleaned = result.replace("\b", "").strip()
        return cleaned

    def _format_action_invocation(self, action: argparse.Action) -> str:
        if not action.option_strings:
            metavar = self._format_args(action, action.dest)
            return metavar or action.dest

        default = self._get_default_metavar_for_optional(action)
        args_string = self._format_args(action, default)

        try:
            import argparse as _argparse

            is_bool = isinstance(action, _argparse._StoreTrueAction) or isinstance(
                action, _argparse.BooleanOptionalAction
            )
        except Exception:
            is_bool = False

        if is_bool:
            return ", ".join(self._primary_boolean_option_strings(action))

        if len(action.option_strings) == 1:
            return action.option_strings[0] + (f" {args_string}" if args_string else "")

        return ", ".join(action.option_strings) + (f" {args_string}" if args_string else "")

    def _format_action(self, action: argparse.Action) -> str:
        if isinstance(action, argparse._SubParsersAction):
            subactions = list(self._iter_indented_subactions(action))
            if not subactions:
                return ""

            help_layout = self._get_help_layout()
            target_help_col = (
                help_layout.help_position
                if help_layout is not None and isinstance(help_layout.help_position, int)
                else None
            )

            invocations = [self._format_action_invocation(sub) for sub in subactions]
            max_name_len = max((len(name) for name in invocations), default=0)
            lines: list[str] = []
            for subaction, invocation in zip(subactions, invocations, strict=False):
                raw_help = getattr(subaction, "help", None)
                help_text = ""
                if raw_help not in (None, argparse.SUPPRESS):
                    help_text = " ".join(str(self._expand_help(subaction)).split())
                if help_text:
                    if target_help_col is None:
                        pad = max_name_len - len(invocation) + 2
                    else:
                        pad = max(2, target_help_col - (2 + len(invocation)))
                    lines.append(f"  {invocation}{' ' * pad}{help_text}\n")
                else:
                    lines.append(f"  {invocation}\n")
            return "".join(lines)

        help_layout = self._get_help_layout()
        if (
            help_layout is None
            or not isinstance(help_layout.help_position, int)
            or not action.option_strings
        ):
            return super()._format_action(action)

        previous_max_help_position = self._max_help_position
        previous_action_max_length = self._action_max_length
        self._max_help_position = help_layout.help_position
        self._action_max_length = max(self._action_max_length, help_layout.help_position - 2)
        try:
            return super()._format_action(action)
        finally:
            self._max_help_position = previous_max_help_position
            self._action_max_length = previous_action_max_length

    def _fill_text(self, text: str, width: int, indent: str) -> str:
        """
        Doesn't strip whitespace from the beginning of the line when formatting help text.
        Code from: https://stackoverflow.com/a/74368128/18588657
        """
        lines = textwrap.dedent(text).splitlines()
        wrapped_lines: list[str] = []

        for line in lines:
            indented = f"{indent}{line}" if line else indent.rstrip()
            stripped = indented.lstrip()
            if not stripped:
                wrapped_lines.append(indented)
                continue

            leading = indented[: len(indented) - len(stripped)]
            column_match = re.match(r"^(\s*\S(?:.*\S)?\s{2,})(\S.*)$", indented)
            if column_match is not None:
                head = column_match.group(1)
                body = column_match.group(2)
                wrapped_lines.append(
                    textwrap.fill(
                        body,
                        width=width,
                        initial_indent=head,
                        subsequent_indent=" " * ansi_len(head),
                        break_long_words=False,
                        break_on_hyphens=False,
                    )
                )
                continue

            wrapped_lines.append(
                textwrap.fill(
                    stripped,
                    width=width,
                    initial_indent=leading,
                    subsequent_indent=leading,
                    break_long_words=False,
                    break_on_hyphens=False,
                )
            )

        return "\n".join(wrapped_lines)

    def _format_usage(
        self,
        usage: str | None,
        actions: Iterable[argparse.Action],
        groups: Iterable[argparse._MutuallyExclusiveGroup],
        prefix: str | None,
    ) -> str:
        """
        Making sure that doesn't crash your program if your terminal window isn't wide enough.
        Explained here: https://stackoverflow.com/a/50394665/18588657
        """
        if prefix is None:
            prefix = "usage: "

        layout = self._get_help_layout()
        if layout is not None:
            custom_prefix = getattr(layout, "usage_prefix", None)
            if custom_prefix is not None:
                prefix = custom_prefix
                usage_style = getattr(layout, "usage_style", None)
                if usage_style is not None:
                    prefix = with_style(prefix, usage_style)

        if usage is not None:
            usage = usage % dict(prog=self._prog)
        elif usage is None and not actions:
            usage = "{prog}".format(**dict(prog=self._prog))
        elif usage is None:
            bool_actions = [a for a in actions if isinstance(a, argparse.BooleanOptionalAction)]
            original_option_strings: dict[argparse.Action, list[str]] = {}
            for action in bool_actions:
                original_option_strings[action] = list(action.option_strings)
                action.option_strings = self._primary_boolean_usage_option_strings(action)

            prog = "{prog}".format(**dict(prog=self._prog))
            optionals = []
            positionals = []
            for action in actions:
                if action.option_strings:
                    optionals.append(action)
                else:
                    positionals.append(action)

            format_actions = self._compat_format_actions_usage
            action_usage = format_actions(optionals + positionals, groups)
            usage = " ".join([s for s in [prog, action_usage] if s])

            text_width = self._width - self._current_indent
            prefix_len = ansi_len(prefix)
            if prefix_len + len(usage) > text_width:
                part_regexp = r"\(.*?\)+(?=\s|$)|" r"\[.*?\]+(?=\s|$)|" r"\S+"
                opt_usage = format_actions(optionals, groups)
                pos_usage = format_actions(positionals, groups)
                opt_parts = re.findall(part_regexp, opt_usage)
                pos_parts = re.findall(part_regexp, pos_usage)

                def get_lines(
                    parts: list[str], indent: str, prefix: str | None = None
                ) -> list[str]:
                    lines, line = [], []
                    if prefix is not None:
                        line_len = ansi_len(prefix) - 1
                    else:
                        line_len = len(indent) - 1
                    for part in parts:
                        if line_len + 1 + len(part) > text_width and line:
                            lines.append(indent + " ".join(line))
                            line = []
                            line_len = len(indent) - 1
                        line.append(part)
                        line_len += len(part) + 1
                    if line:
                        lines.append(indent + " ".join(line))
                    if prefix is not None:
                        lines[0] = lines[0][len(indent) :]
                    return lines

                if prefix_len + len(prog) <= 0.75 * text_width:
                    indent = " " * (prefix_len + len(prog) + 1)
                    if opt_parts:
                        lines = get_lines([prog, *opt_parts], indent, prefix)
                        lines.extend(get_lines(pos_parts, indent))
                    elif pos_parts:
                        lines = get_lines([prog, *pos_parts], indent, prefix)
                    else:
                        lines = [prog]

                else:
                    indent = " " * prefix_len
                    parts = opt_parts + pos_parts
                    lines = get_lines(parts, indent)
                    if len(lines) > 1:
                        lines = []
                        lines.extend(get_lines(opt_parts, indent))
                        lines.extend(get_lines(pos_parts, indent))
                    lines = [prog, *lines]

                usage = "\n".join(lines)

            for action, option_strings in original_option_strings.items():
                action.option_strings = option_strings

        usage_text_style = None
        if layout is not None:
            custom_prefix = getattr(layout, "usage_prefix", None)
            if isinstance(usage, str) and custom_prefix is not None:
                usage = re.sub(
                    r"^(?:\x1b\[[0-9;]*m)*\s*usage:\s*",
                    "",
                    usage,
                    flags=re.IGNORECASE,
                )
            usage_text_style = getattr(layout, "usage_text_style", None)
        if usage_text_style is not None and isinstance(usage, str):
            usage = with_style(usage, usage_text_style)

        return f"{prefix}{usage}\n\n"


__all__ = ["InterfacyHelpFormatter"]

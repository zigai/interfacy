import argparse
import os
import re
import textwrap
from collections.abc import Iterable
from typing import TYPE_CHECKING

from stdl.st import ansi_len, with_style

if TYPE_CHECKING:
    from interfacy.appearance.layout import HelpLayout


class InterfacyHelpFormatter(argparse.HelpFormatter):
    """Help formatter that integrates Interfacy layout settings."""

    def set_help_layout(self, help_layout: "HelpLayout") -> None:
        """
        Attach a HelpLayout for formatting decisions.

        Args:
            help_layout (HelpLayout): Layout instance to use.
        """
        self._interfacy_help_layout = help_layout

    def _get_help_layout(self) -> "HelpLayout | None":
        return getattr(self, "_interfacy_help_layout", None)

    def start_section(self, heading: str | None) -> None:  # type: ignore[override]
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
        return [text]

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
            shorts = [
                s for s in action.option_strings if s.startswith("-") and not s.startswith("--")
            ]
            longs = [s for s in action.option_strings if s.startswith("--")]

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
            primary_long = (
                no_flag if bool(default_val) else (base_flag or (longs[0] if longs else ""))
            )

            if shorts:
                return shorts[0] + (f", {primary_long}" if primary_long else "")
            return primary_long

        if len(action.option_strings) == 1:
            return action.option_strings[0] + (f" {args_string}" if args_string else "")

        return ", ".join(action.option_strings) + (f" {args_string}" if args_string else "")

    def _format_action(self, action: argparse.Action) -> str:
        action_header = self._format_action_invocation(action)
        help_layout = self._get_help_layout()
        help_position = self._action_max_length + 4
        if help_layout is not None and isinstance(help_layout.help_position, int):
            help_position = max(help_layout.help_position, self._action_max_length + 2)
        indent_len = 2

        if not action.help:
            return f"{' ' * indent_len}{action_header}\n"

        try:
            term_width = os.get_terminal_size().columns
        except (OSError, AttributeError):
            term_width = 80

        help_width = term_width - help_position - indent_len
        help_text = self._expand_help(action)

        padding_len = help_position - len(action_header) - indent_len

        wrapped_lines: list[str] = []
        for word in help_text.split():
            if not wrapped_lines:
                wrapped_lines.append(word)
            else:
                if ansi_len(wrapped_lines[-1]) + ansi_len(word) + 1 <= help_width:
                    wrapped_lines[-1] = f"{wrapped_lines[-1]} {word}"
                else:
                    wrapped_lines.append(word)

        result = [f"{' ' * indent_len}{action_header}{' ' * padding_len}{wrapped_lines[0]}"]
        if len(wrapped_lines) > 1:
            for line in wrapped_lines[1:]:
                result.append(f"{' ' * help_position}{line}")

        return "\n".join(result) + "\n"

    def _fill_text(self, text: str, width: int, indent: str) -> str:
        """
        Doesn't strip whitespace from the beginning of the line when formatting help text.
        Code from: https://stackoverflow.com/a/74368128/18588657
        """
        text = textwrap.dedent(text)
        text = textwrap.indent(text, indent)
        text = text.splitlines()  # type: ignore[assignment]
        text = [textwrap.fill(line, width) for line in text]  # type: ignore[union-attr]
        text = "\n".join(text)  # type: ignore[arg-type]
        return text

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
            prog = "{prog}".format(**dict(prog=self._prog))
            optionals = []
            positionals = []
            for action in actions:
                if action.option_strings:
                    optionals.append(action)
                else:
                    positionals.append(action)

            format = self._format_actions_usage
            action_usage = format(optionals + positionals, groups)
            usage = " ".join([s for s in [prog, action_usage] if s])

            text_width = self._width - self._current_indent
            prefix_len = ansi_len(prefix)
            if prefix_len + len(usage) > text_width:
                part_regexp = r"\(.*?\)+(?=\s|$)|" r"\[.*?\]+(?=\s|$)|" r"\S+"
                opt_usage = format(optionals, groups)
                pos_usage = format(positionals, groups)
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

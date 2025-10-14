import argparse
import os
import re
import textwrap
from typing import TYPE_CHECKING

from objinspect.util import colored_type
from stdl.st import ansi_len, with_style

if TYPE_CHECKING:
    from interfacy.appearance.layout import HelpLayout


class InterfacyHelpFormatter(argparse.HelpFormatter):
    PRE_FMT_PREFIX = "\x00FMT:"

    def set_help_layout(self, help_layout: "HelpLayout") -> None:
        self._interfacy_help_layout = help_layout

    def _get_help_layout(self) -> "HelpLayout | None":
        return getattr(self, "_interfacy_help_layout", None)

    def _split_lines(self, text, width):
        # return text.splitlines()
        return [text]

    def _format_args(self, action, default_metavar: str):
        result = super()._format_args(action, default_metavar)
        return result.strip()

    def _format_action_invocation(self, action):
        if not action.option_strings:
            metavar = self._format_args(action, action.dest)
            return metavar or action.dest

        default = self._get_default_metavar_for_optional(action)
        args_string = self._format_args(action, default)

        if len(action.option_strings) == 1:
            return action.option_strings[0] + (f" {args_string}" if args_string else "")

        return f"{action.option_strings[0]}, {action.option_strings[1]}"

    def _format_action(self, action):
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

        # preformatted line support from theme/arg schema
        if isinstance(help_text, str) and help_text.startswith(self.PRE_FMT_PREFIX):
            formatted = help_text[len(self.PRE_FMT_PREFIX) :]
            return f"{' ' * indent_len}{formatted}\n"

        # If help_layout chooses template layout, build preformatted output for all actions (including -h)
        if help_layout is not None:
            mode = help_layout.layout_mode
            has_templates = bool(help_layout.format_option or help_layout.format_positional)
            use_template = (mode == "template") or (mode == "auto" and has_templates)
            if use_template:
                formatted = self._format_with_layout_template(action, help_layout, help_text)
                if formatted is not None:
                    return f"{' ' * indent_len}{formatted}\n"
        padding_len = help_position - len(action_header) - indent_len

        # respect terminal width
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

    def _format_with_layout_template(
        self,
        action: argparse.Action,
        layout: "HelpLayout",
        help_text: str | None,
    ) -> str | None:
        style = layout.style

        is_option = bool(action.option_strings)
        template = layout.format_option if is_option else layout.format_positional
        if not template:
            return None

        include_meta = layout.include_metavar_in_flag_display
        if is_option:
            default_metavar = self._get_default_metavar_for_optional(action)
            args_string = self._format_args(action, default_metavar) if include_meta else ""
            shorts = [
                s for s in action.option_strings if s.startswith("-") and not s.startswith("--")
            ]
            longs = [s for s in action.option_strings if s.startswith("--")]

            is_bool = isinstance(action, argparse._StoreTrueAction) or (
                isinstance(action, argparse.BooleanOptionalAction)
            )
            if is_bool and longs:
                base_flag = None
                no_flag = None
                for flag in longs:
                    if flag.startswith("--no-"):
                        no_flag = flag
                    else:
                        base_flag = flag

                default_val = action.default
                if default_val is True and no_flag:  # default is True: show --no- flag
                    primary_long = no_flag
                else:  # default is False/None: show positive flag
                    primary_long = base_flag or longs[0]

                longs = [primary_long]

            flag_short = (shorts[0] + (f" {args_string}" if args_string else "")) if shorts else ""
            flag_long = (longs[0] + (f" {args_string}" if args_string else "")) if longs else ""
            flag = ", ".join([p for p in (flag_short, flag_long) if p])
        else:
            metavar = action.metavar or action.dest
            flag_short = ""
            flag_long = ""
            flag = metavar

        description = help_text or ""
        if description:
            description = with_style(description, style.description)

        t_str = ""
        if action.type not in (None, str, int, float, bool):
            try:
                t_str = colored_type(action.type, style.type)
            except Exception:
                t_str = ""

        default_val = action.default
        is_bool = isinstance(action, argparse._StoreTrueAction) or (
            isinstance(action, argparse.BooleanOptionalAction)
        )
        default_raw = ""
        if is_bool:
            default_raw = "true" if bool(default_val) else "false"
        elif (
            action.option_strings
            and default_val is not None
            and default_val is not argparse.SUPPRESS
        ):
            default_raw = str(default_val)

        # Special-case help action to show [default]
        if set(action.option_strings) & {"-h", "--help"}:
            default_raw = layout.default_label_for_help

        width = layout.default_field_width
        styled_default = with_style(default_raw, style.default) if default_raw else ""
        pad = max(0, width - ansi_len(styled_default))
        default_padded = f"{' ' * pad}{styled_default}"
        default = styled_default

        values = {
            "flag": flag,
            "flag_short": flag_short,
            "flag_long": flag_long,
            "description": description,
            "type": t_str,
            "default": default,
            "default_padded": default_padded,
            "choices": "",
            "extra": "",
            "required": (getattr(action, "required", False) and layout.required_indicator) or "",
            "metavar": action.metavar or action.dest,
        }

        styled_cols = layout._build_styled_columns(flag_short, flag_long, flag, is_option)
        values.update(styled_cols)

        values["desc_line"] = description
        if values.get("required"):
            values["desc_line"] = f"{description} {values['required']}"

        values["details"] = ""

        try:
            rendered = template.format(**values)
        except Exception:
            rendered = f"{values['flag']:<40} {values['description']}"

        # Clean up empty type markers like " [type: ]" and drop metavars when disabled
        rendered = re.sub(r"\s*\[type:\s*\]", "", rendered)
        if not include_meta:
            rendered = re.sub(r"(\-\w+)\s+[A-Z][A-Z0-9_-]*", r"\1", rendered)
            rendered = re.sub(
                r"(\-\-[A-Za-z0-9][A-Za-z0-9\-]*)\s+[A-Z][A-Z0-9_-]*", r"\1", rendered
            )
        return rendered

    def _fill_text(self, text, width, indent):
        """
        Doesn't strip whitespace from the beginning of the line when formatting help text.
        Code from: https://stackoverflow.com/a/74368128/18588657
        """
        # Strip the indent from the original python definition that plagues most of us.
        text = textwrap.dedent(text)
        text = textwrap.indent(text, indent)  # Apply any requested indent.
        text = text.splitlines()  # Make a list of lines
        text = [textwrap.fill(line, width) for line in text]  # Wrap each line
        text = "\n".join(text)  # Join the lines again
        return text

    def _format_usage(self, usage, actions, groups, prefix):
        """
        Making sure that doesn't crash your program if your terminal window isn't wide enough.
        Explained here: https://stackoverflow.com/a/50394665/18588657
        """
        if prefix is None:
            prefix = "usage: "
        # if usage is specified, use that
        if usage is not None:
            usage = usage % dict(prog=self._prog)
        # if no optionals or positionals are available, usage is just prog
        elif usage is None and not actions:
            usage = "{prog}".format(**dict(prog=self._prog))
        # if optionals and positionals are available, calculate usage
        elif usage is None:
            prog = "{prog}".format(**dict(prog=self._prog))
            # split optionals from positionals
            optionals = []
            positionals = []
            for action in actions:
                if action.option_strings:
                    optionals.append(action)
                else:
                    positionals.append(action)

            # build full usage string
            format = self._format_actions_usage
            action_usage = format(optionals + positionals, groups)
            usage = " ".join([s for s in [prog, action_usage] if s])

            # wrap the usage parts if it's too long
            text_width = self._width - self._current_indent
            if len(prefix) + len(usage) > text_width:
                # break usage into wrappable parts
                part_regexp = r"\(.*?\)+(?=\s|$)|" r"\[.*?\]+(?=\s|$)|" r"\S+"
                opt_usage = format(optionals, groups)
                pos_usage = format(positionals, groups)
                opt_parts = re.findall(part_regexp, opt_usage)
                pos_parts = re.findall(part_regexp, pos_usage)

                # NOTE: only change from original code is commenting out the assert statements
                # assert " ".join(opt_parts) == opt_usage
                # assert " ".join(pos_parts) == pos_usage

                # helper for wrapping lines
                def get_lines(parts, indent, prefix=None):
                    lines, line = [], []
                    if prefix is not None:
                        line_len = len(prefix) - 1
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

                # if prog is short, follow it with optionals or positionals
                if len(prefix) + len(prog) <= 0.75 * text_width:
                    indent = " " * (len(prefix) + len(prog) + 1)
                    if opt_parts:
                        lines = get_lines([prog, *opt_parts], indent, prefix)
                        lines.extend(get_lines(pos_parts, indent))
                    elif pos_parts:
                        lines = get_lines([prog, *pos_parts], indent, prefix)
                    else:
                        lines = [prog]

                # if prog is long, put it on its own line
                else:
                    indent = " " * len(prefix)
                    parts = opt_parts + pos_parts
                    lines = get_lines(parts, indent)
                    if len(lines) > 1:
                        lines = []
                        lines.extend(get_lines(opt_parts, indent))
                        lines.extend(get_lines(pos_parts, indent))
                    lines = [prog, *lines]

                usage = "\n".join(lines)

        return f"{prefix}{usage}\n\n"

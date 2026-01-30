import argparse
import os
import re
import textwrap
from collections.abc import Iterable
from enum import Enum
from inspect import Parameter as StdParameter
from types import SimpleNamespace
from typing import TYPE_CHECKING

from stdl.st import ansi_len, with_style

from interfacy.util import format_default_for_help, format_type_for_help

if TYPE_CHECKING:
    from interfacy.appearance.layout import HelpLayout


class InterfacyHelpFormatter(argparse.HelpFormatter):
    PRE_FMT_PREFIX = "\x00FMT:"
    DEFAULT_TERM_RATIO = 5

    def set_help_layout(self, help_layout: "HelpLayout") -> None:
        self._interfacy_help_layout = help_layout

    def _get_help_layout(self) -> "HelpLayout | None":
        return getattr(self, "_interfacy_help_layout", None)

    def start_section(self, heading: str | None) -> None:  # type: ignore[override]
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

    def _layout_uses_default_column(self, layout: "HelpLayout") -> bool:
        template = layout.format_option or ""
        return "{default_padded}" in template

    def _get_default_raw(self, action: argparse.Action, layout: "HelpLayout") -> str:
        if set(action.option_strings) & {"-h", "--help"}:
            return ""

        is_bool = isinstance(action, argparse._StoreTrueAction) or (
            isinstance(action, argparse.BooleanOptionalAction)
        )
        default_val = getattr(action, "default", None)
        if is_bool:
            return "true" if bool(default_val) else "false"

        if (
            action.option_strings
            and default_val is not None
            and default_val is not argparse.SUPPRESS
        ):
            return format_default_for_help(default_val)
        return ""

    def _compute_default_field_width(
        self,
        actions: list[argparse.Action],
        layout: "HelpLayout",
    ) -> int | None:
        if not self._layout_uses_default_column(layout):
            return None

        defaults = [self._get_default_raw(action, layout) for action in actions]
        lengths = [len(d) for d in defaults if d]
        base_width = (
            layout._get_default_field_width_base()
            if hasattr(layout, "_get_default_field_width_base")
            else layout.default_field_width
        )
        if not lengths:
            return base_width

        try:
            term_width = os.get_terminal_size().columns
        except (OSError, AttributeError):
            term_width = 80

        ratio = getattr(layout, "default_field_width_term_ratio", self.DEFAULT_TERM_RATIO)
        term_cap = max(base_width, term_width // max(1, ratio))
        soft_ratio = getattr(layout, "default_field_width_soft_ratio", 8)
        soft_cap = max(base_width, term_width // max(1, soft_ratio))
        effective_cap = min(term_cap, soft_cap)
        max_cap = getattr(layout, "default_field_width_max", None)
        if max_cap is not None:
            effective_cap = min(effective_cap, max_cap)

        candidates = [length for length in lengths if length <= effective_cap]
        if not candidates:
            return base_width

        candidates.sort()
        count = len(candidates)
        small_size = getattr(layout, "default_field_width_small_sample_size", 6)
        if count <= small_size:
            width = max(candidates)
        else:
            percentile = getattr(layout, "default_field_width_percentile", 0.75)
            percentile = min(max(percentile, 0.0), 1.0)
            idx = max(0, min(count - 1, int((percentile * count + 0.999999) - 1)))
            width = candidates[idx]
        return max(base_width, width)

    def prepare_layout(self, actions: list[argparse.Action]) -> None:
        layout = self._get_help_layout()
        if layout is None:
            return

        if not self._layout_uses_default_column(layout):
            return

        computed = self._compute_default_field_width(actions, layout)
        if computed is not None:
            layout.default_field_width = computed

    def _split_lines(self, text: str, width: int) -> list[str]:
        # return text.splitlines()
        return [text]

    def _format_args(self, action: argparse.Action, default_metavar: str) -> str:
        result = super()._format_args(action, default_metavar)
        # Treat the special "\b" metavar (used to hide metavars) as empty
        cleaned = result.replace("\b", "").strip()
        return cleaned

    def _format_action_invocation(self, action: argparse.Action) -> str:
        if not action.option_strings:
            metavar = self._format_args(action, action.dest)
            return metavar or action.dest

        default = self._get_default_metavar_for_optional(action)
        args_string = self._format_args(action, default)

        try:  # show --no-flag when default=True
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

        if (
            help_layout is not None
            and isinstance(help_text, str)
            and not help_text.startswith(self.PRE_FMT_PREFIX)
            and set(action.option_strings) & {"-h", "--help"}
            and help_layout._use_template_layout()
        ):
            param_stub = SimpleNamespace(
                name="help",
                kind=StdParameter.KEYWORD_ONLY,
                description=help_text,
                is_typed=False,
                type=None,
                is_required=False,
                has_default=False,
                default=None,
                is_optional=False,
            )
            formatted = help_layout.format_parameter(param_stub, tuple(action.option_strings))
            if isinstance(formatted, str) and formatted.startswith(self.PRE_FMT_PREFIX):
                formatted = formatted[len(self.PRE_FMT_PREFIX) :]
                indent = " " * indent_len
                lines = str(formatted).splitlines()
                lines = [indent + line for line in lines]
                return "\n".join(lines) + "\n"

        if isinstance(help_text, str) and help_text.startswith(self.PRE_FMT_PREFIX):
            formatted = help_text[len(self.PRE_FMT_PREFIX) :]
            indent = " " * indent_len
            lines = str(formatted).splitlines()
            lines = [indent + line for line in lines]
            return "\n".join(lines) + "\n"

        # If help_layout chooses template layout, build preformatted output for all actions (including -h)
        if help_layout is not None:
            mode = help_layout.layout_mode
            has_templates = bool(help_layout.format_option or help_layout.format_positional)
            use_template = (mode == "template") or (mode == "auto" and has_templates)
            if use_template:
                formatted = self._format_with_layout_template(action, help_layout, help_text)
                if formatted is not None:
                    indent = " " * indent_len
                    lines = str(formatted).splitlines()
                    lines = [indent + line for line in lines]
                    return "\n".join(lines) + "\n"
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
            metavar = action.metavar or default_metavar
            args_string = self._format_args(action, metavar) if include_meta else ""
            if args_string and getattr(layout, "dashify_metavar", False):
                args_string = args_string.replace("_", "-")
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
            flag = " ".join(metavar) if isinstance(metavar, tuple) else metavar

        raw_description = help_text or ""
        description = ""

        type_str = ""
        try:
            if action.type in (None, bool):
                type_str = ""
            elif action.type in (str, int, float):
                type_str = ""
            else:
                type_str = format_type_for_help(action.type, style.type)
        except Exception:
            type_str = ""

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
            default_raw = format_default_for_help(default_val)

        # Special-case help action to hide default label
        if set(action.option_strings) & {"-h", "--help"}:
            default_raw = ""

        width = layout.default_field_width
        styled_default = with_style(default_raw, style.default) if default_raw else ""
        pad = max(0, width - ansi_len(styled_default))
        default_padded = f"{' ' * pad}{styled_default}"
        default = styled_default
        styled_cols = layout._build_styled_columns(flag_short, flag_long, flag, is_option)
        indent_len = 2  # must match the indent used in _format_action

        try:
            term_width = os.get_terminal_size().columns
        except (OSError, AttributeError):
            term_width = 80

        if is_option:
            col_width = (
                ansi_len(styled_cols.get("flag_short_col", ""))
                + ansi_len(styled_cols.get("flag_long_col", ""))
                + 1
            )
        else:
            col_width = ansi_len(styled_cols.get("flag_col", "")) + 1

        wrap_width = max(10, term_width - indent_len - col_width)
        cont_indent = " " * (indent_len + col_width)
        desc_lines: list[str] = []

        if raw_description:
            for word in raw_description.split():
                if not desc_lines:
                    desc_lines.append(word)
                else:
                    if len(desc_lines[-1]) + 1 + len(word) <= wrap_width:
                        desc_lines[-1] = f"{desc_lines[-1]} {word}"
                    else:
                        desc_lines.append(word)

        req_indicator = (action.required and layout.required_indicator) or ""

        if desc_lines:
            styled_desc_lines = [with_style(line, style.description) for line in desc_lines]
            first = styled_desc_lines[0] + (f" {req_indicator}" if req_indicator else "")
            if len(styled_desc_lines) > 1:
                rest = [cont_indent + line for line in styled_desc_lines[1:]]
                description = "\n".join([first, *rest])
            else:
                description = first
        else:
            description = ""

        default_overflow = ""
        if default_raw and "{default_padded}" in template and ansi_len(styled_default) > width:
            overflow_mode = getattr(layout, "default_overflow_mode", "newline")
            if overflow_mode == "inline":
                default_overflow = ""
                default_padded = styled_default
                default = styled_default
            else:
                default_overflow = default_raw
                styled_default = ""
                default_padded = " " * width
                default = ""

        if default_overflow:
            arrow = with_style("→", style.extra_data)
            overflow_label = "default:"
            overflow_value = with_style(default_overflow, style.default)
            overflow_line = f"{arrow} {overflow_label} {overflow_value}"
            if description:
                description = f"{description}\n{cont_indent}{overflow_line}"
            else:
                description = f"\n{cont_indent}{overflow_line}"

        values = {
            "flag": flag,
            "flag_short": flag_short,
            "flag_long": flag_long,
            "description": description,
            "type": type_str,
            "default": default,
            "default_padded": default_padded,
            "choices": "",
            "extra": "",
            "required": req_indicator,
            "metavar": action.metavar or action.dest,
        }

        if hasattr(layout, "column_gap"):
            gap = layout.column_gap
            if getattr(layout, "collapse_gap_when_no_description", False) and not description:
                gap = getattr(layout, "no_description_gap", "") if values.get("extra") else ""
            values["column_gap"] = gap

        values.update(styled_cols)
        values["desc_line"] = description

        def format_choice(value: object) -> str:
            if isinstance(value, Enum):
                raw = value.value
                if isinstance(raw, str):
                    return raw
                return value.name
            return str(value)

        choices_str = ""
        choices_label = ""
        choices_block = ""

        try:
            if action.choices:
                choices_str = ", ".join([format_choice(i) for i in action.choices])
        except Exception:
            choices_str = ""

        if choices_str and getattr(layout, "hide_type_when_choices", True):
            type_str = ""
            values["type"] = ""

        detail_parts: list[str] = []

        if default:
            detail_parts.append("default: " + default)
        if type_str:
            detail_parts.append("type: " + type_str)

        choices_styled = ""
        if choices_str:
            choices_styled = ", ".join(
                [with_style(format_choice(i), style.string) for i in action.choices]
            )
            choices_label = "choices:"
            choices_block = f" [{choices_label} {choices_styled}]"
            detail_parts.append(choices_label + " " + choices_styled)

        if detail_parts:
            is_option = bool(action.option_strings)
            if is_option:
                pad_count = layout.short_flag_width + layout.long_flag_width + 2
            else:
                pad_count = layout.pos_flag_width + 2
            arrow = with_style("↳", style.extra_data)
            details_text = with_style(" | ", style.extra_data).join(detail_parts)
            values["details"] = "\n" + (" " * pad_count) + f"{arrow} " + details_text
        else:
            values["details"] = ""

        values["choices"] = choices_str
        values["choices_label"] = choices_label
        values["choices_block"] = choices_block
        if getattr(layout, "use_action_extra", False):
            extra_parts: list[str] = []
            if default and not is_bool:
                label_text = getattr(layout, "default_label_text", "default:")
                extra_parts.append(f"[{label_text} {default}]")
            if choices_str:
                label_text = getattr(layout, "choices_label_text", "choices:")
                extra_parts.append(f"[{label_text} {choices_styled}]")
            if extra_parts:
                joiner = " ".join(extra_parts)
                values["extra"] = f" {joiner}" if description else joiner
            else:
                values["extra"] = ""

        try:
            rendered = template.format(**values)
        except Exception:
            rendered = f"{values['flag']:<40} {values['description']}"

        rendered = re.sub(r"\s*\[type:\s*\]", "", rendered)
        if (
            is_option
            and set(action.option_strings) & {"-h", "--help"}
            and getattr(layout, "suppress_empty_default_brackets_for_help", False)
        ):
            rendered = re.sub(r"\[\s*\]\s*", "", rendered)
        return rendered

    def _fill_text(self, text: str, width: int, indent: str) -> str:
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
            prefix_len = ansi_len(prefix)
            if prefix_len + len(usage) > text_width:
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

                # if prog is short, follow it with optionals or positionals
                if prefix_len + len(prog) <= 0.75 * text_width:
                    indent = " " * (prefix_len + len(prog) + 1)
                    if opt_parts:
                        lines = get_lines([prog, *opt_parts], indent, prefix)
                        lines.extend(get_lines(pos_parts, indent))
                    elif pos_parts:
                        lines = get_lines([prog, *pos_parts], indent, prefix)
                    else:
                        lines = [prog]

                # if prog is long, put it on its own line
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

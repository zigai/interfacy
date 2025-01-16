import argparse
import os
import re
import textwrap

from stdl.st import len_without_ansi


class InterfacyHelpFormatter(argparse.HelpFormatter):

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

        return "{}, {}".format(action.option_strings[0], action.option_strings[1])

    def _format_action(self, action):
        action_header = self._format_action_invocation(action)
        help_position = max(40, self._action_max_length + 4)
        indent_len = 2

        if not action.help:
            return f"{' ' * indent_len}{action_header}\n"

        term_width = os.get_terminal_size().columns
        help_width = term_width - help_position - indent_len

        help_text = self._expand_help(action)
        padding_len = help_position - len(action_header) - indent_len

        # respect terminal width
        wrapped_lines: list[str] = []
        for word in help_text.split():
            if not wrapped_lines:
                wrapped_lines.append(word)
            else:
                if len_without_ansi(wrapped_lines[-1]) + len_without_ansi(word) + 1 <= help_width:
                    wrapped_lines[-1] = f"{wrapped_lines[-1]} {word}"
                else:
                    wrapped_lines.append(word)

        result = [f"{' ' * indent_len}{action_header}{' ' * padding_len}{wrapped_lines[0]}"]
        if len(wrapped_lines) > 1:
            for line in wrapped_lines[1:]:
                result.append(f"{' ' * help_position}{line}")

        return "\n".join(result) + "\n"

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
            usage = "%(prog)s" % dict(prog=self._prog)
        # if optionals and positionals are available, calculate usage
        elif usage is None:
            prog = "%(prog)s" % dict(prog=self._prog)
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
                        lines = get_lines([prog] + opt_parts, indent, prefix)
                        lines.extend(get_lines(pos_parts, indent))
                    elif pos_parts:
                        lines = get_lines([prog] + pos_parts, indent, prefix)
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
                    lines = [prog] + lines

                usage = "\n".join(lines)

        return f"{prefix}{usage}\n\n"

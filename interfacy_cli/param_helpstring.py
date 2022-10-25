from py_inspect import Parameter
from py_inspect.util import type_to_str
from stdl.str_u import colored


class HelpStringTheme:
    def __init__(
        self,
        type_clr: str,
        default_clr: str,
        sep: str,
        simplify_type: bool = False,
        clear_metavar: bool = False,
    ) -> None:
        self.type_clr = type_clr
        self.default_cr = default_clr
        self.sep = sep
        self.simplify_type = simplify_type
        self.clear_metavar = clear_metavar

    @property
    def dict(self):
        return {
            "type_clr": self.type_clr,
            "default_clr": self.default_cr,
            "sep": self.sep,
            "simplify_type": self.simplify_type,
            "clear_metavar": self.clear_metavar,
        }


def param_helpstring(param: Parameter, theme: HelpStringTheme) -> str:
    if param.is_required and not param.is_typed:
        return ""
    help_str = []
    if param.is_typed:
        typestr = type_to_str(param.type)
        if theme.simplify_type:
            typestr = typestr.split(".")[-1]
        help_str.append(colored(typestr, theme.type_clr))
    if param.is_typed and param.is_optional:
        help_str.append(theme.sep)
    if param.is_optional:
        help_str.append(f"{colored(param.default, theme.default_cr)}")
    help_str = "".join(help_str)
    if param.description is not None:
        help_str = f"{param.description} [{help_str}]"
    return help_str


import re
from argparse import HelpFormatter

try:
    from gettext import gettext as _
    from gettext import ngettext
except ImportError:

    def _(message):
        return message

    def ngettext(singular, plural, n):
        if n == 1:
            return singular
        else:
            return plural


class SafeHelpFormatter(HelpFormatter):
    """
    Helpstring formatter that doesn't crash your program if your terminal windows isn't wide enough.
    Explained here: https://stackoverflow.com/a/50394665/18588657
    """

    def _format_usage(self, usage, actions, groups, prefix):
        if prefix is None:
            prefix = _("usage: ")

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
                # XXX
                # assert " ".join(opt_parts) == opt_usage
                # assert " ".join(pos_parts) == pos_usage

                # helper for wrapping lines
                def get_lines(parts, indent, prefix=None):
                    lines = []
                    line = []
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

                # join lines into usage
                usage = "\n".join(lines)

        # prefix with 'usage:'
        return "%s%s\n\n" % (prefix, usage)


__all__ = ["HelpStringTheme", "param_helpstring", "SafeHelpFormatter"]

from py_inspect import Class, Function, Parameter
from py_inspect.util import type_to_str
from stdl.str_u import FG, colored

from interfacy_cli.safe_help_formatter import SafeRawHelpFormatter


def with_style(text: str, style: dict) -> str:
    return colored(text, **style)


class Theme:
    clear_metavar: bool
    formatter_class = SafeRawHelpFormatter

    def __init__(self) -> None:
        ...

    def get_parameter_help(self, param: Parameter) -> str:
        raise NotImplementedError

    def get_commands_epilog(self, *args: Class | Function) -> str:
        raise NotImplementedError

    def format_description(self, desc: str) -> str:
        return desc

    def get_top_level_epilog(self, *args: Class | Function) -> str:
        raise NotImplementedError


class DefaultTheme(Theme):
    simplify_typenames = True
    clear_metavar = True
    style_type = dict(color=FG.GREEN)
    style_default = dict(color=FG.LIGHT_BLUE)
    style_description = dict(color=FG.GRAY)
    sep = " = "
    min_ljust = 16

    def get_parameter_help(self, param: Parameter) -> str:
        """
        Returns a parameter helpstring that should be paseed as help to argparse.ArgumentParser
        """
        if param.is_required and not param.is_typed:
            return ""
        help_str = []
        if param.is_typed:
            typestr = type_to_str(param.type)
            if self.simplify_typenames:
                typestr = typestr.split(".")[-1]
            help_str.append(with_style(typestr, self.style_type))
        if param.is_typed and param.is_optional:
            help_str.append(self.sep)
        if param.is_optional:
            help_str.append(with_style(param.default, self.style_default))
        help_str = "".join(help_str)
        if param.description is not None:
            help_str = f"[{help_str}] {with_style(param.description, self.style_description)}"
        return help_str

    def _command_desc(self, val: Function | Class, ljust: int):
        name = f"  {val.name}".ljust(ljust)
        return f"{name} {with_style(val.description, self.style_description)}"

    def get_top_level_epilog(self, *args: Class | Function):
        ljust = max(self.min_ljust, max([len(i.name) for i in args]))
        s = ["commands:"]
        for i in args:
            s.append(self._command_desc(i, ljust))
        return "\n".join(s)

    def get_class_commands_epilog(self, cmd: Class):
        ljust = max(self.min_ljust, max([len(i.name) for i in cmd.methods]))
        s = ["commands:"]
        for i in cmd.methods:
            if i.name == "__init__":
                continue
            s.append(self._command_desc(i, ljust))
        return "\n".join(s)


class PlainTheme(DefaultTheme):
    simplify_typenames = True
    clear_metavar = True
    style_type = dict(color=FG.WHITE)
    style_default = dict(color=FG.WHITE)
    style_description = dict(color=FG.WHITE)


class LegacyTheme(DefaultTheme):
    simplify_typenames = False
    sep = ", default: "
    type_color = FG.LIGHT_YELLOW
    style_type = dict(color=FG.LIGHT_YELLOW)
    param_default_color = dict(color=FG.LIGHT_BLUE)


__all__ = [
    "Theme",
    "DefaultTheme",
    "PlainTheme",
    "LegacyTheme",
]

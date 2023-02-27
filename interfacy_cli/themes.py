from objinspect import Class, Function, Parameter
from objinspect.util import type_to_str
from stdl.str_u import FG, colored

from interfacy_cli.theme import Theme, with_style


class DefaultTheme(Theme):
    simplify_types = True
    clear_metavar = True
    style_type = dict(color=FG.GREEN)
    style_default = dict(color=FG.LIGHT_BLUE)
    style_description = dict(color=FG.GRAY)
    sep = " = "
    min_ljust = 19
    required_indicator = "(" + colored("*", color=FG.RED) + ") "

    def get_parameter_help(self, param: Parameter) -> str:
        """
        Returns a parameter helpstring that should be paseed as help to argparse.ArgumentParser
        """
        if param.is_required and not param.is_typed:
            return ""
        help_str = []

        if param.is_typed:
            typestr = type_to_str(param.type)
            if self.simplify_types:
                typestr = typestr.split(".")[-1]
                typestr = typestr.replace("| None", "").strip()
            help_str.append(with_style(typestr, self.style_type))

        if param.is_typed and param.is_optional and param.default is not None:
            help_str.append(self.sep)

        if param.is_optional and param.default is not None:
            help_str.append(with_style(param.default, self.style_default))

        help_str = "".join(help_str)

        if param.description is not None:
            """
            current_len = len(help_str)
            if current_len < 24:
                fill = " " * (24 - current_len)
            else:
                fill = " "
            """
            fill = " "
            help_str = f"{help_str} | {fill}{with_style(param.description, self.style_description)}"
        if param.is_required:
            help_str = f"{help_str} {self.required_indicator}"
        return help_str

    def _command_desc(self, val: Function | Class, ljust: int):
        name = f"  {val.name}".ljust(ljust)
        return f"{name} {with_style(val.description, self.style_description)}"

    def get_commands_help(self, *args: Class | Function):
        ljust = max(self.min_ljust, max([len(i.name) for i in args]))
        s = ["commands:"]
        for i in args:
            s.append(self._command_desc(i, ljust))
        return "\n".join(s)

    def get_class_commands_help(self, cmd: Class):
        ljust = max(self.min_ljust, max([len(i.name) for i in cmd.methods]))
        s = ["commands:"]
        for i in cmd.methods:
            if i.name == "__init__":
                continue
            s.append(self._command_desc(i, ljust))
        return "\n".join(s)


class PlainTheme(DefaultTheme):
    style_type = dict(color=FG.WHITE)
    style_default = dict(color=FG.WHITE)
    style_description = dict(color=FG.WHITE)
    required_indicator = "(required)"


class LegacyTheme(DefaultTheme):
    simplify_types = False
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

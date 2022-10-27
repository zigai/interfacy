from py_inspect import Class, Function, Parameter
from py_inspect.util import type_to_str
from stdl.str_u import FG, colored

from interfacy_cli.safe_help_formatter import SafeRawHelpFormatter


class Theme:
    clear_metavar: bool
    formatter_class = SafeRawHelpFormatter

    def __init__(self) -> None:
        ...

    def get_parameter_help(self, param: Parameter) -> str:
        raise NotImplementedError

    def get_commands_epilog(self, *args: Class | Function) -> str:
        raise NotImplementedError

    def format_description(self, desc: str):
        raise NotImplementedError


class Default(Theme):
    simplify_typename = True
    clear_metavar = True
    type_color = FG.GREEN
    param_default_color = FG.LIGHT_BLUE
    description_color = FG.GRAY
    type_default_sep = " = "
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
            if self.simplify_typename:
                typestr = typestr.split(".")[-1]
            help_str.append(colored(typestr, self.type_color))
        if param.is_typed and param.is_optional:
            help_str.append(self.type_default_sep)
        if param.is_optional:
            help_str.append(f"{colored(param.default, self.param_default_color)}")
        help_str = "".join(help_str)
        if param.description is not None:
            desc = colored(param.description, self.description_color)
            help_str = f"[{help_str}] {desc}"
        return help_str

    def command_desc(self, val: Function | Class, ljust: int):
        name = f"  {val.name}".ljust(ljust)
        return f"{name} {colored(val.description,self.description_color)}"

    def get_top_level_epilog(self, *args: Class | Function):
        ljust = max(self.min_ljust, max([len(i.name) for i in args]))
        s = ["commands:"]
        for i in args:
            s.append(self.command_desc(i, ljust))
        return "\n".join(s)

    def get_class_commands_epilog(self, cmd: Class):
        ljust = max(self.min_ljust, max([len(i.name) for i in cmd.methods]))
        s = ["commands:"]
        for i in cmd.methods:
            if i.name == "__init__":
                continue
            s.append(self.command_desc(i, ljust))
        return "\n".join(s)

    def format_description(self, desc: str):
        return desc


class Plain(Default):
    simplify_typename = False
    clear_metavar = False
    type_color = FG.WHITE
    param_default_color = FG.WHITE
    description_color = FG.WHITE
    type_default_sep = " = "


class Legacy(Default):
    simplify_typename = False
    type_default_sep = ", default: "
    type_color = FG.LIGHT_YELLOW
    param_default_color = FG.LIGHT_BLUE


__all__ = [
    "Theme",
    "Default",
    "Plain",
    "Legacy",
]

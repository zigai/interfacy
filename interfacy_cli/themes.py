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

    def get_commands_desc(self, *args: Class | Function) -> str:
        raise NotImplementedError


class Default(Theme):
    simplify_typename = True
    clear_metavar = True
    type_color = FG.GREEN
    param_default_color = FG.LIGHT_BLUE
    description_color = FG.GRAY
    type_default_sep = " = "

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

    def get_commands_desc(self, *args: Class | Function) -> str:
        def get_max_param_len(args, mn: int = 12):
            mx = mn
            for i in args:
                if isinstance(i, Class):
                    for j in i.methods:
                        if j.name == "__init__":
                            continue
                        mx = max(mx, len(j.name))
                else:
                    mx = max(mx, len(i.name))
            return mx

        mx = get_max_param_len(args)

        def command_desc(val: Function | Class):
            name = f"  {val.name}".ljust(mx)
            return f"{name}  {colored(val.description,self.description_color)}"

        s = ["commands:"]
        for i in args:
            if isinstance(i, Class):
                for j in i.methods:
                    if j.name == "__init__":
                        continue
                    s.append(command_desc(j))
            else:
                s.append(command_desc(i))
        return "\n".join(s)


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

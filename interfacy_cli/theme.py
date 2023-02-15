from objinspect import Class, Function, Parameter
from stdl.str_u import colored

from interfacy_cli.safe_help_formatter import SafeRawHelpFormatter


class Theme:
    clear_metavar: bool
    formatter_class = SafeRawHelpFormatter

    def get_parameter_help(self, param: Parameter) -> str:
        raise NotImplementedError

    def get_commands_epilog(self, *args: Class | Function) -> str:
        raise NotImplementedError

    def format_description(self, desc: str) -> str:
        return desc

    def get_top_level_epilog(self, *args: Class | Function) -> str:
        raise NotImplementedError


def with_style(text: str, style: dict) -> str:
    return colored(text, **style)

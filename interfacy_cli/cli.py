import typing as T

from strto import StrToTypeParser

from interfacy_cli.argparse_parser import ArgparseParser
from interfacy_cli.click_parser import ClickParser
from interfacy_cli.exceptions import InterfacyException
from interfacy_cli.themes import InterfacyTheme


class CLI:
    def __init__(
        self,
        *commands: T.Callable,
        run: bool = True,
        description: str | None = None,
        epilog: str | None = None,
        backend: T.Literal["argparse", "click"] = "argparse",
        value_parser: StrToTypeParser | None = None,
        theme: InterfacyTheme | None = None,
        flag_strategy: T.Literal["keyword_only", "required_positional"] = "required_positional",
        flag_translation_mode: T.Literal["none", "kebab", "snake"] = "kebab",
        from_file_prefix: str = "@F",
        print_result: bool = True,
        add_abbrevs: bool = True,
        read_stdin: bool = False,
        allow_args_from_file: bool = True,
        tab_completion: bool = False,
        **kwargs,
    ):
        self.backend = backend
        if self.backend not in ["argparse", "click"]:
            raise ValueError(f"Invalid backend: {self.backend}. Must be one of 'argparse', 'click'")
        parser_cls = ArgparseParser if self.backend == "argparse" else ClickParser

        self.parser = parser_cls(
            description=description,
            epilog=epilog,
            theme=theme,
            value_parser=value_parser,
            flag_strategy=flag_strategy,
            flag_translation_mode=flag_translation_mode,
            from_file_prefix=from_file_prefix,
            print_result=print_result,
            add_abbrevs=add_abbrevs,
            read_stdin=read_stdin,
            allow_args_from_file=allow_args_from_file,
            tab_completion=tab_completion,
            **kwargs,
        )
        self.commands = commands
        if run:
            self.run()

    def run(self, args: list[str] | None = None) -> T.Any:
        try:
            return self.parser.run(*self.commands, args=args)
        except InterfacyException as e:
            self.parser.log(str(e))


__all__ = ["CLI"]

from argparse import Action, FileType
from typing import Any, Callable, Iterable, Type

from nested_argparse import NestedArgumentParser
from strto import get_parser

from interfacy_cli.safe_help_formatter import SafeRawHelpFormatter


class InterfacyArgumentParser:
    formater_class = SafeRawHelpFormatter
    parser_class = NestedArgumentParser

    def __init__(
        self,
        desciption: str | None = None,
        epilog: str | None = None,
        from_file_prefix: str = "@F",
        allow_args_from_file: bool = True,
        install_tab_completion: bool = False,
    ) -> None:
        self.from_file_prefix = from_file_prefix
        self.allow_args_from_file = allow_args_from_file
        self.install_tab_completion = install_tab_completion

        self._parser = self.parser_class(
            formatter_class=self.formater_class,
            description=desciption,
            epilog=epilog,
        )

    @property
    def description(self) -> str | None:
        return self._parser.description

    @property
    def epilog(self) -> str | None:
        return self._parser.epilog

    @property
    def parser(self):
        return self._parser

    def set_description(self, description: str | None = None) -> None:
        self._parser.description = description

    def set_epilog(self, epilog: str | None = None) -> None:
        self._parser.epilog = epilog

    def add_argument(
        self,
        *name_or_flags: str,
        action: str | Type[Action] | None = ...,
        nargs: int | str | None = ...,
        default: Any = ...,
        type: Any = ...,
        choices: Iterable | None = None,
        required: bool = False,
        help: str | None = None,
        const: Any = ...,
        metavar: str | tuple[str, ...] | None = None,
        dest: str | None = None
    ) -> None:
        # TODO: type
        self._parser.add_argument(
            *name_or_flags,
            action=action,  # type:ignore
            nargs=nargs,  # type:ignore
            default=default,
            choices=choices,
            required=required,
            help=help,
            const=const,
            metavar=metavar,
            dest=dest,
        )

    def parse_args(self):
        ...

    def add_subparsers(self):
        ...

    def get_args(self):
        ...

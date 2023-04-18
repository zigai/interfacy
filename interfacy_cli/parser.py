import sys
from functools import partial

import strto
from nested_argparse import NestedArgumentParser

from interfacy_cli.argparse_wrappers import SafeRawHelpFormatter, _ArgumentParser
from interfacy_cli.util import get_args


class InterfacyArgumentParser:
    def __init__(
        self,
        desciption: str | None = None,
        epilog: str | None = None,
        from_file_prefix: str = "@F",
        allow_args_from_file: bool = True,
        type_parser: strto.Parser | None = None,
        formatter_class=SafeRawHelpFormatter,
    ) -> None:
        self.from_file_prefix = from_file_prefix
        self.allow_args_from_file = allow_args_from_file
        self.type_parser = type_parser or strto.get_parser()
        self.formatter_class = formatter_class

        self._parser: NestedArgumentParser = _ArgumentParser(
            formatter_class=self.formatter_class,
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
    def parser(self) -> NestedArgumentParser:
        return self._parser

    def set_description(self, description: str | None = None) -> None:
        self._parser.description = description

    def set_epilog(self, epilog: str | None = None) -> None:
        self._parser.epilog = epilog

    def add_argument(self, *args, **kwargs):
        if "type" in kwargs:
            func = partial(self.type_parser.parse, t=kwargs["type"])
            kwargs["type"] = func
        return self._parser.add_argument(*args, **kwargs)

    def parse_args(self, args: list[str] | None = None):
        if args is None:
            args = self.get_args()
        return self._parser.parse_args(args)

    def add_subparsers(self, *args, **kwargs):
        return self._parser.add_subparsers(*args, **kwargs)

    def get_args(self) -> list[str]:
        if self.allow_args_from_file:
            return get_args(sys.argv, from_file_prefix=self.from_file_prefix)
        return sys.argv[1:]


__all__ = ["InterfacyArgumentParser"]

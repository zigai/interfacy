from typing import TYPE_CHECKING, Any

from interfacy.runner import COMMAND_KEY_BASE, SchemaRunner

if TYPE_CHECKING:
    from interfacy.argparse_backend.argparser import Argparser
    from interfacy.argparse_backend.argument_parser import ArgumentParser


class ArgparseRunner(SchemaRunner):
    """
    Execute parsed CLI commands against inspected callables.

    Args:
        namespace (dict[str, Any]): Parsed argument namespace.
        builder (Argparser): Parser instance that built the schema.
        args (list[str]): Raw CLI arguments.
        parser (ArgumentParser): ArgumentParser used for parsing.
    """

    def __init__(
        self,
        namespace: dict[str, Any],
        builder: "Argparser",
        args: list[str],
        parser: "ArgumentParser",
    ) -> None:
        self._parser = parser
        super().__init__(namespace=namespace, builder=builder, args=args)


__all__ = [
    "COMMAND_KEY_BASE",
    "ArgparseRunner",
]

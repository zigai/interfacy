"""Backend-neutral help rendering for tests."""

import click

from interfacy import Interfacy


def render_help(parser: Interfacy) -> str:
    """Render root help text through the parser's native backend object."""
    native = parser.build_parser()
    if parser.backend == "click":
        return native.get_help(click.Context(native))

    return native.format_help()

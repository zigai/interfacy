from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from interfacy.help.layouts.aligned import Aligned, AlignedTyped
    from interfacy.help.layouts.argparse_style import ArgparseLayout
    from interfacy.help.layouts.base import HelpLayout
    from interfacy.help.layouts.clap import ClapLayout
    from interfacy.help.layouts.default import InterfacyLayout
    from interfacy.help.layouts.modern import Modern
    from interfacy.help.layouts.standard import StandardLayout

# Exports load on first access, so a run imports only the layout it uses.
_EXPORTS = {
    "Aligned": "interfacy.help.layouts.aligned",
    "AlignedTyped": "interfacy.help.layouts.aligned",
    "ArgparseLayout": "interfacy.help.layouts.argparse_style",
    "ClapLayout": "interfacy.help.layouts.clap",
    "HelpLayout": "interfacy.help.layouts.base",
    "InterfacyLayout": "interfacy.help.layouts.default",
    "Modern": "interfacy.help.layouts.modern",
    "StandardLayout": "interfacy.help.layouts.standard",
}


def __getattr__(name: str) -> Any:
    try:
        module_name = _EXPORTS[name]
    except KeyError as e:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from e

    from importlib import import_module

    return getattr(import_module(module_name), name)


__all__ = [
    "Aligned",
    "AlignedTyped",
    "ArgparseLayout",
    "ClapLayout",
    "HelpLayout",
    "InterfacyLayout",
    "Modern",
    "StandardLayout",
]

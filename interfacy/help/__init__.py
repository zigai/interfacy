from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from interfacy.help.colors import InterfacyColors
    from interfacy.help.content import (
        HelpContent,
        HelpContext,
        HelpRenderer,
        HelpResult,
        HelpSection,
        HelpSectionKind,
        default_help_renderer,
    )
    from interfacy.help.diagnostics import DiagnosticContent, DiagnosticLayout, DiagnosticResult
    from interfacy.help.layouts import (
        Aligned,
        AlignedTyped,
        ArgparseLayout,
        ClapLayout,
        HelpLayout,
        InterfacyLayout,
        Modern,
        StandardLayout,
    )
    from interfacy.help.style import HelpStyle

# Exports load on first access, so a run imports only the layout it uses.
_EXPORTS = {
    "Aligned": "interfacy.help.layouts",
    "AlignedTyped": "interfacy.help.layouts",
    "ArgparseLayout": "interfacy.help.layouts",
    "ClapLayout": "interfacy.help.layouts",
    "DiagnosticContent": "interfacy.help.diagnostics",
    "DiagnosticLayout": "interfacy.help.diagnostics",
    "DiagnosticResult": "interfacy.help.diagnostics",
    "HelpContent": "interfacy.help.content",
    "HelpContext": "interfacy.help.content",
    "HelpLayout": "interfacy.help.layouts",
    "HelpRenderer": "interfacy.help.content",
    "HelpResult": "interfacy.help.content",
    "HelpSection": "interfacy.help.content",
    "HelpSectionKind": "interfacy.help.content",
    "HelpStyle": "interfacy.help.style",
    "InterfacyColors": "interfacy.help.colors",
    "InterfacyLayout": "interfacy.help.layouts",
    "Modern": "interfacy.help.layouts",
    "StandardLayout": "interfacy.help.layouts",
    "default_help_renderer": "interfacy.help.content",
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
    "DiagnosticContent",
    "DiagnosticLayout",
    "DiagnosticResult",
    "HelpContent",
    "HelpContext",
    "HelpLayout",
    "HelpRenderer",
    "HelpResult",
    "HelpSection",
    "HelpSectionKind",
    "HelpStyle",
    "InterfacyColors",
    "InterfacyLayout",
    "Modern",
    "StandardLayout",
    "default_help_renderer",
]

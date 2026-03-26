from __future__ import annotations

import os
from importlib.metadata import version as package_version

project = "Interfacy"
author = "Žiga Ivanšek"
copyright = "2026, Žiga Ivanšek"
release = package_version("interfacy")
version = release

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
    "sphinxcontrib.mermaid",
    "notfound.extension",
    "sphinxext.opengraph",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "myst",
}
root_doc = "index"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "smartquotes",
]
myst_heading_anchors = 3

autoclass_content = "both"
autodoc_class_signature = "separated"
autodoc_member_order = "bysource"
autodoc_preserve_defaults = True
autodoc_typehints = "description"
autodoc_typehints_description_target = "documented"
autodoc_typehints_format = "short"
add_module_names = False
default_role = "any"
python_use_unqualified_type_names = True
python_maximum_signature_line_length = 68

napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_preprocess_types = False
napoleon_type_aliases = {
    "AbbreviationGenerator": ":class:`interfacy.naming.AbbreviationGenerator`",
    "Argument": ":class:`interfacy.schema.schema.Argument`",
    "ArgumentParser": ":class:`interfacy.argparse_backend.argument_parser.ArgumentParser`",
    "Class": "``Class``",
    "Command": ":class:`interfacy.schema.schema.Command`",
    "CommandEntry": ":class:`interfacy.group.CommandEntry`",
    "CommandNameRegistry": ":class:`interfacy.naming.CommandNameRegistry`",
    "FlagStrategy": ":class:`interfacy.naming.FlagStrategy`",
    "Function": "``Function``",
    "HelpLayout": ":class:`interfacy.appearance.HelpLayout`",
    "HelpOptionSortRule": ":data:`interfacy.appearance.help_sort.HelpOptionSortRule`",
    "HelpSubcommandSortRule": ":data:`interfacy.appearance.help_sort.HelpSubcommandSortRule`",
    "InterfacyClickCommand": ":class:`interfacy.click_backend.commands.InterfacyClickCommand`",
    "InterfacyClickGroup": ":class:`interfacy.click_backend.commands.InterfacyClickGroup`",
    "InterfacyColors": ":class:`interfacy.appearance.InterfacyColors`",
    "InterfacyParser": ":class:`interfacy.core.InterfacyParser`",
    "Method": "``Method``",
    "Parameter": "``Parameter``",
    "ParserSchema": ":class:`interfacy.schema.schema.ParserSchema`",
    "PipeTargets": ":class:`interfacy.pipe.PipeTargets`",
    "StrToTypeParser": "``StrToTypeParser``",
    "SubgroupEntry": ":class:`interfacy.group.SubgroupEntry`",
    "argparse.HelpFormatter": ":class:`argparse.HelpFormatter`",
    "click.core.Command": ":class:`click.Command`",
}

autodoc_type_aliases = {
    "AbbreviationGenerator": "interfacy.naming.AbbreviationGenerator",
    "Argument": "interfacy.schema.schema.Argument",
    "ArgumentParser": "interfacy.argparse_backend.argument_parser.ArgumentParser",
    "CommandType": "interfacy.schema.schema.CommandType",
    "Command": "interfacy.schema.schema.Command",
    "CommandEntry": "interfacy.group.CommandEntry",
    "FlagStrategy": "interfacy.naming.FlagStrategy",
    "HelpLayout": "interfacy.appearance.HelpLayout",
    "HelpOptionSortRule": "interfacy.appearance.help_sort.HelpOptionSortRule",
    "HelpSubcommandSortRule": "interfacy.appearance.help_sort.HelpSubcommandSortRule",
    "InterfacyClickCommand": "interfacy.click_backend.commands.InterfacyClickCommand",
    "InterfacyClickGroup": "interfacy.click_backend.commands.InterfacyClickGroup",
    "InterfacyColors": "interfacy.appearance.InterfacyColors",
    "ParserSchema": "interfacy.schema.schema.ParserSchema",
    "PipePriority": "interfacy.pipe.PipePriority",
    "PipeTargets": "interfacy.pipe.PipeTargets",
    "StrToTypeParser": "strto.StrToTypeParser",
    "SubgroupEntry": "interfacy.group.SubgroupEntry",
    "TargetsInput": "interfacy.pipe.TargetsInput",
    "argparse.HelpFormatter": "argparse.HelpFormatter",
    "interfacy.appearance.layout.InterfacyColors": "interfacy.appearance.InterfacyColors",
    "interfacy.appearance.help_sort.HelpOptionSortRule": "interfacy.appearance.help_sort.HelpOptionSortRule",
    "interfacy.appearance.help_sort.HelpSubcommandSortRule": "interfacy.appearance.help_sort.HelpSubcommandSortRule",
    "interfacy.appearance.layouts.HelpLayout": "interfacy.appearance.HelpLayout",
}

intersphinx_mapping = {
    "click": ("https://click.palletsprojects.com/en/stable/", "_intersphinx/click.inv"),
    "python": ("https://docs.python.org/3", "_intersphinx/python.inv"),
}

nitpick_ignore = [
    ("py:class", "'interfacy.appearance.help_sort.HelpOptionSortRule'"),
    ("py:class", "'interfacy.appearance.help_sort.HelpSubcommandSortRule'"),
    ("py:class", "AbbreviationGenerator"),
    ("py:class", "Argument"),
    ("py:class", "Class"),
    ("py:class", "Command"),
    ("py:class", "FlagStrategy"),
    ("py:class", "Function"),
    ("py:class", "HelpOptionSortRule"),
    ("py:class", "HelpSubcommandSortRule"),
    ("py:class", "InterfacyParser"),
    ("py:class", "Method"),
    ("py:class", "Parameter"),
    ("py:class", "ParserSchema"),
    ("py:class", "PipeTargets"),
    ("py:class", "StrToTypeParser"),
    ("py:class", "collections.abc.Callable"),
    ("py:class", "interfacy.appearance.help_sort.T"),
    ("py:class", "interfacy.argparse_backend.argument_parser.ArgumentParser"),
    ("py:class", "interfacy.click_backend.commands.InterfacyClickCommand"),
    ("py:class", "interfacy.click_backend.commands.InterfacyClickGroup"),
    ("py:class", "interfacy.core.InterfacyParser"),
    ("py:class", "interfacy.group.CommandEntry"),
    ("py:class", "interfacy.group.SubgroupEntry"),
    ("py:class", "objinspect.method.Method"),
    ("py:class", "optional"),
    ("py:class", "TypeAliasForwardRef"),
]

html_theme = "sphinx_book_theme"
html_title = project
html_show_sourcelink = False
html_baseurl = os.environ.get("READTHEDOCS_CANONICAL_URL", "")
ogp_social_cards = {"enable": False}

html_theme_options = {
    "path_to_docs": "docs",
    "repository_branch": "master",
    "repository_url": "https://github.com/zigai/interfacy",
    "use_repository_button": True,
    "use_source_button": True,
}

html_context = {}
if os.environ.get("READTHEDOCS"):
    html_context["READTHEDOCS"] = True

if html_baseurl:
    ogp_site_url = html_baseurl

notfound_urls_prefix = "/"

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
autodoc_typehints_description_target = "documented_params"
autodoc_typehints_format = "short"
add_module_names = False
python_use_unqualified_type_names = True
python_maximum_signature_line_length = 68

napoleon_google_docstring = True
napoleon_numpy_docstring = False

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

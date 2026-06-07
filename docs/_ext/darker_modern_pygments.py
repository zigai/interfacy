from __future__ import annotations

import keyword
from collections.abc import Iterator

from pygments.lexers.python import PythonLexer
from pygments.style import Style
from pygments.token import (
    Comment,
    Error,
    Generic,
    Keyword,
    Literal,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
    Text,
    Token,
)

PYTHON_RESERVED_KEYWORDS = set(keyword.kwlist) - {"False", "None", "True"}

BUILTIN_TYPES = {
    "bool",
    "bytes",
    "complex",
    "dict",
    "float",
    "frozenset",
    "int",
    "list",
    "object",
    "set",
    "str",
    "tuple",
    "type",
}

TokenItem = tuple[int, Token, str]


def is_whitespace(token: Token, value: str) -> bool:
    return token in Text and not value.strip()


def next_significant(tokens: list[TokenItem], start: int) -> TokenItem | None:
    for item in tokens[start:]:
        if not is_whitespace(item[1], item[2]):
            return item
    return None


def previous_significant(tokens: list[TokenItem], start: int) -> TokenItem | None:
    for item in reversed(tokens[:start]):
        if not is_whitespace(item[1], item[2]):
            return item
    return None


def is_capitalized_name(value: str) -> bool:
    return bool(value) and value[0].isupper()


def darker_modern_token(
    token: Token,
    value: str,
    *,
    previous_value: str,
    next_value: str,
) -> Token:
    resolved = token
    if (token in Keyword or token is Operator.Word) and value in PYTHON_RESERVED_KEYWORDS:
        resolved = Keyword.Reserved
    elif token is Name.Namespace:
        resolved = Name
    elif token in Name.Builtin and value in BUILTIN_TYPES:
        resolved = Name.Class
    elif token in Name.Builtin and next_value == "(":
        resolved = Name.Function
    elif token is Name and is_capitalized_name(value):
        resolved = Name.Class
    elif token is Name and (next_value == "(" or (previous_value == "." and next_value == "(")):
        resolved = Name.Function
    return resolved


class DarkerModernPythonLexer(PythonLexer):
    """Python lexer tuned to VS Code's Darker Modern semantic colors."""

    name = "Darker Modern Python"
    aliases = ["python", "py", "python3", "py3"]

    def get_tokens_unprocessed(self, text: str) -> Iterator[TokenItem]:
        tokens = list(super().get_tokens_unprocessed(text))

        for position, (index, token, value) in enumerate(tokens):
            previous_token = previous_significant(tokens, position)
            next_token = next_significant(tokens, position + 1)
            yield (
                index,
                darker_modern_token(
                    token,
                    value,
                    previous_value=previous_token[2] if previous_token else "",
                    next_value=next_token[2] if next_token else "",
                ),
                value,
            )


class DarkerModernStyle(Style):
    name = "darker-modern"
    background_color = "#080808"
    highlight_color = "#2b2b2b"
    line_number_color = "#6e7681"
    line_number_background_color = "#080808"
    line_number_special_color = "#cccccc"
    line_number_special_background_color = "#181818"

    styles = {
        Text: "#eeffff",
        Comment: "#6A9955",
        Comment.Preproc: "#569cd6",
        Comment.Special: "#d7ba7d",
        Keyword: "#569cd6",
        Keyword.Constant: "#569cd6",
        Keyword.Declaration: "#569cd6",
        Keyword.Namespace: "#569cd6",
        Keyword.Pseudo: "#569cd6",
        Keyword.Reserved: "#C586C0",
        Keyword.Type: "#4EC9B0",
        Operator: "#d4d4d4",
        Operator.Word: "#569cd6",
        Punctuation: "#d4d4d4",
        Name: "#9CDCFE",
        Name.Attribute: "#9CDCFE",
        Name.Builtin: "#569cd6",
        Name.Builtin.Pseudo: "#569cd6",
        Name.Class: "#4EC9B0",
        Name.Constant: "#4FC1FF",
        Name.Decorator: "#DCDCAA",
        Name.Entity: "#569cd6",
        Name.Exception: "#4EC9B0",
        Name.Function: "#DCDCAA",
        Name.Label: "#C8C8C8",
        Name.Namespace: "#4EC9B0",
        Name.Tag: "#569cd6",
        Name.Variable: "#9CDCFE",
        Name.Variable.Class: "#9CDCFE",
        Name.Variable.Global: "#9CDCFE",
        Name.Variable.Instance: "#9CDCFE",
        Literal: "#ce9178",
        Literal.Date: "#b5cea8",
        String: "#ce9178",
        String.Affix: "#569cd6",
        String.Backtick: "#ce9178",
        String.Char: "#ce9178",
        String.Delimiter: "#ce9178",
        String.Doc: "#ce9178",
        String.Double: "#ce9178",
        String.Escape: "#d7ba7d",
        String.Heredoc: "#ce9178",
        String.Interpol: "#569cd6",
        String.Other: "#ce9178",
        String.Regex: "#d16969",
        String.Single: "#ce9178",
        String.Symbol: "#ce9178",
        Number: "#b5cea8",
        Number.Bin: "#b5cea8",
        Number.Float: "#b5cea8",
        Number.Hex: "#b5cea8",
        Number.Integer: "#b5cea8",
        Number.Oct: "#b5cea8",
        Generic.Deleted: "#f85149",
        Generic.Emph: "italic",
        Generic.Error: "#f85149",
        Generic.Heading: "#569cd6 bold",
        Generic.Inserted: "#2ea043",
        Generic.Output: "#eeffff",
        Generic.Prompt: "#6e7681",
        Generic.Strong: "bold",
        Generic.Subheading: "#569cd6 bold",
        Generic.Traceback: "#f85149",
        Error: "#f85149 bg:#3c1f1e",
    }

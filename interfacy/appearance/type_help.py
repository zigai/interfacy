from types import NoneType
from typing import Protocol

from objinspect.typing import is_union_type, type_args, type_origin
from stdl.st import TextStyle, with_style

from interfacy.util import resolve_type_alias, simplified_type_name


class TypeStyleTheme(Protocol):
    type_keyword: TextStyle
    type_bracket: TextStyle
    type_punctuation: TextStyle
    type_operator: TextStyle
    type_literal: TextStyle


def format_type_for_help(
    annotation: object,
    style: TextStyle,
    theme: TypeStyleTheme | None = None,
) -> str:
    return TypeHelpFormatter(style, theme=theme).format(annotation)


class TypeHelpFormatter:
    _TYPE_BRACKETS = frozenset("[](){}")
    _TYPE_PUNCTUATION = frozenset({",", ":"})
    _TYPE_OPERATORS = frozenset({"|", "?"})
    _TYPE_KEYWORDS = frozenset(
        {
            "Annotated",
            "Any",
            "ClassVar",
            "Final",
            "Literal",
            "Never",
            "NoReturn",
            "None",
            "NoneType",
            "NotRequired",
            "Optional",
            "Required",
            "Self",
            "TypeAlias",
            "TypeGuard",
            "TypeVar",
            "Union",
        }
    )

    def __init__(
        self,
        style: TextStyle,
        *,
        theme: TypeStyleTheme | None = None,
    ) -> None:
        self.style = style
        self.theme = theme
        self.token_styles = self._resolve_type_token_styles()

    def format(self, annotation: object) -> str:
        type_text = self._stringify(annotation)
        rendered: list[str] = []
        for kind, value in self._tokenize(type_text):
            if kind == "space":
                rendered.append(value)
            else:
                rendered.append(with_style(value, self.token_styles.get(kind, self.style)))
        return "".join(rendered)

    def _resolve_type_token_styles(self) -> dict[str, TextStyle]:
        def pick(name: str) -> TextStyle:
            if self.theme is not None and hasattr(self.theme, name):
                return getattr(self.theme, name)
            return self.style

        return {
            "name": self.style,
            "keyword": pick("type_keyword"),
            "bracket": pick("type_bracket"),
            "punctuation": pick("type_punctuation"),
            "operator": pick("type_operator"),
            "literal": pick("type_literal"),
            "other": self.style,
        }

    def _stringify(self, annotation: object) -> str:
        if isinstance(annotation, str):
            return simplified_type_name(annotation)

        resolved = resolve_type_alias(annotation)
        optional_union_name = self._stringify_optional_union_type(resolved)
        if optional_union_name is not None:
            return optional_union_name

        generic_type_name = self._stringify_generic_type(resolved)
        if generic_type_name is not None:
            return generic_type_name

        return simplified_type_name(self._stringify_fallback_type_name(resolved))

    def _stringify_optional_union_type(self, annotation: object) -> str | None:
        try:
            if not is_union_type(annotation):
                return None
            args = list(type_args(annotation))
        except (AttributeError, KeyError, NameError, TypeError, ValueError):
            return None

        if len(args) != 2 or not any(arg is NoneType for arg in args):
            return None

        base = next((arg for arg in args if arg is not NoneType), None)
        if base is None:
            return "Any?"

        base_name = self._stringify(base)
        if base_name.endswith("?"):
            return base_name
        return f"{base_name}?"

    @staticmethod
    def _safe_stringify(value: object) -> str:
        try:
            return str(value)
        except (RecursionError, TypeError, ValueError):
            return object.__repr__(value)

    def _stringify_generic_type(self, annotation: object) -> str | None:
        try:
            origin = type_origin(annotation)
            args = type_args(annotation)
        except (AttributeError, KeyError, NameError, TypeError, ValueError):
            return None

        if origin is None or not args:
            return None

        return simplified_type_name(self._safe_stringify(annotation))

    def _stringify_fallback_type_name(self, annotation: object) -> str:
        if isinstance(annotation, type):
            return annotation.__name__

        name = getattr(annotation, "__name__", None)
        if isinstance(name, str):
            return name

        return self._safe_stringify(annotation)

    @staticmethod
    def _consume_space(text: str, start: int) -> int:
        index = start + 1
        while index < len(text) and text[index].isspace():
            index += 1
        return index

    @staticmethod
    def _consume_quoted_literal(text: str, start: int) -> int:
        quote = text[start]
        index = start + 1
        escaped = False
        while index < len(text):
            current = text[index]
            if escaped:
                escaped = False
            elif current == "\\":
                escaped = True
            elif current == quote:
                index += 1
                break
            index += 1
        return index

    @staticmethod
    def _consume_numeric_literal(text: str, start: int) -> int:
        index = start + 1
        while index < len(text) and (text[index].isdigit() or text[index] == "."):
            index += 1
        return index

    @staticmethod
    def _consume_identifier(text: str, start: int) -> int:
        index = start + 1
        while index < len(text) and (text[index].isalnum() or text[index] in {"_", "."}):
            index += 1
        return index

    def _next_type_token(self, type_text: str, start: int) -> tuple[str, str, int]:
        ch = type_text[start]
        kind = "other"
        value = ch
        next_index = start + 1

        if ch.isspace():
            next_index = self._consume_space(type_text, start)
            kind = "space"
            value = type_text[start:next_index]
        elif ch in self._TYPE_BRACKETS:
            kind = "bracket"
        elif ch in self._TYPE_PUNCTUATION:
            kind = "punctuation"
        elif ch in self._TYPE_OPERATORS:
            kind = "operator"
        elif ch in {"'", '"'}:
            next_index = self._consume_quoted_literal(type_text, start)
            kind = "literal"
            value = type_text[start:next_index]
        elif ch.isdigit():
            next_index = self._consume_numeric_literal(type_text, start)
            kind = "literal"
            value = type_text[start:next_index]
        elif ch.isalpha() or ch == "_":
            next_index = self._consume_identifier(type_text, start)
            value = type_text[start:next_index]
            kind = "keyword" if value in self._TYPE_KEYWORDS else "name"

        return kind, value, next_index

    def _tokenize(self, type_text: str) -> list[tuple[str, str]]:
        tokens: list[tuple[str, str]] = []
        index = 0
        while index < len(type_text):
            kind, value, index = self._next_type_token(type_text, index)
            tokens.append((kind, value))
        return tokens


__all__ = ["TypeHelpFormatter", "TypeStyleTheme", "format_type_for_help"]

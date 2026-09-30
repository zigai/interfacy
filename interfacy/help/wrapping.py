"""Text wrapping primitives shared by help renderers and layouts."""

import re
import textwrap

from stdl.st import ansi_len


def wrap_visible_words(
    text: str,
    *,
    width: int,
    initial_indent: str = "",
    subsequent_indent: str = "",
) -> list[str]:
    """Wrap words by visible terminal width while preserving ANSI sequences."""
    words = text.split()
    if not words:
        return []

    lines: list[str] = []
    indent = initial_indent
    line_words: list[str] = []
    line_width = ansi_len(indent)
    for word in words:
        word_width = ansi_len(word)
        separator_width = 1 if line_words else 0
        if line_words and line_width + separator_width + word_width > max(10, width):
            lines.append(indent + " ".join(line_words))
            indent = subsequent_indent
            line_words = [word]
            line_width = ansi_len(indent) + word_width
            continue

        line_words.append(word)
        line_width += separator_width + word_width

    if line_words:
        lines.append(indent + " ".join(line_words))

    return lines


def expand_usage_parts(parts: list[str], available_width: int) -> list[str]:
    """Split an over-wide choice token without splitting individual choices."""
    expanded: list[str] = []
    for part in parts:
        if ansi_len(part) <= available_width:
            expanded.append(part)
            continue

        bracket_prefix = ""
        bracket_suffix = ""
        body = part
        if part.startswith("[") and part.endswith("]"):
            bracket_prefix = "["
            bracket_suffix = "]"
            body = part[1:-1]

        if body.startswith("{") and body.endswith("}") and "," in body:
            choices = body[1:-1].split(",")
            for index, choice in enumerate(choices):
                prefix = (bracket_prefix + "{") if index == 0 else ""
                suffix = "}" if index == len(choices) - 1 else ","
                if index == len(choices) - 1:
                    suffix += bracket_suffix
                expanded.append(f"{prefix}{choice}{suffix}")

            continue

        expanded.append(part)

    return expanded


def wrap_usage_parts(
    parts: list[str],
    *,
    width: int,
    prefix_width: int,
    indent: str,
) -> str:
    """Pack usage tokens into terminal-width lines using visible lengths."""
    lines: list[str] = []
    current: list[str] = []
    current_width = prefix_width
    available_width = max(10, width - ansi_len(indent))
    for part in expand_usage_parts(parts, available_width):
        part_width = ansi_len(part)
        separator_width = 1 if current else 0
        if current and current_width + separator_width + part_width > width:
            lines.append(" ".join(current))
            current = [part]
            current_width = ansi_len(indent) + part_width
            continue

        current.append(part)
        current_width += separator_width + part_width

    if current:
        lines.append(" ".join(current))

    if len(lines) <= 1:
        return lines[0] if lines else ""

    return lines[0] + "\n" + "\n".join(indent + line for line in lines[1:])


def wrap_plain_words(text: str, wrap_width: int) -> list[str]:
    """Greedily wrap words into lines no wider than ``wrap_width`` characters."""
    wrapped: list[str] = []
    for word in text.split():
        if not wrapped:
            wrapped.append(word)
        elif len(wrapped[-1]) + 1 + len(word) <= wrap_width:
            wrapped[-1] = f"{wrapped[-1]} {word}"
        else:
            wrapped.append(word)

    return wrapped


def wrap_text_preserving_words(
    text: str,
    *,
    width: int,
    initial_indent: str = "",
    subsequent_indent: str = "",
) -> list[str]:
    """Wrap text without breaking words or hyphenated tokens."""
    return textwrap.wrap(
        text,
        width=max(10, width),
        initial_indent=initial_indent,
        subsequent_indent=subsequent_indent,
        break_long_words=False,
        break_on_hyphens=False,
    )


def metadata_wrap_index(line: str) -> int | None:
    """Return where trailing choice metadata starts in a rendered row, if present."""
    candidates = [
        line.find("[choices:"),
        line.find("[possible values:"),
    ]
    indexes = [idx for idx in candidates if idx > 0]
    if not indexes:
        return None

    return min(indexes)


def wrap_overwide_line(rendered: str, *, terminal_width: int, indent: int = 0) -> str:
    """
    Wrap rendered help lines that exceed the terminal width.

    Args:
        rendered (str): Rendered help text, possibly spanning several lines.
        terminal_width (int): Terminal width in columns.
        indent (int): Leading indent applied to the rendered text.
    """
    width = max(10, terminal_width - indent)
    wrapped_lines: list[str] = []
    for line in rendered.splitlines() or [rendered]:
        if ansi_len(line) <= width:
            wrapped_lines.append(line)
            continue

        metadata_idx = metadata_wrap_index(line)
        if metadata_idx is not None:
            prefix = line[:metadata_idx]
            body = line[metadata_idx:]
            wrapped_lines.extend(
                wrap_text_preserving_words(
                    body.strip(),
                    width=width,
                    initial_indent=prefix,
                    subsequent_indent=" " * ansi_len(prefix),
                )
            )
            continue

        column_match = re.match(r"^(\s*\S(?:.*\S)?\s{2,})(\S.*)$", line)
        if column_match is not None:
            head = column_match.group(1)
            body = column_match.group(2)
            wrapped_lines.extend(
                wrap_text_preserving_words(
                    body.strip(),
                    width=width,
                    initial_indent=head,
                    subsequent_indent=" " * ansi_len(head),
                )
            )
            continue

        leading = len(line) - len(line.lstrip(" "))
        continuation_indent = " " * (leading if leading < width - 10 else 2)
        wrapped = wrap_text_preserving_words(
            line.strip(),
            width=width - 1,
            initial_indent=continuation_indent,
            subsequent_indent=f"{continuation_indent}  ",
        )
        wrapped_lines.extend(wrapped or [line])

    return "\n".join(wrapped_lines)


__all__ = [
    "expand_usage_parts",
    "metadata_wrap_index",
    "wrap_overwide_line",
    "wrap_plain_words",
    "wrap_text_preserving_words",
    "wrap_usage_parts",
    "wrap_visible_words",
]

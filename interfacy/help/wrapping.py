"""ANSI-aware wrapping primitives shared by help renderers."""

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
                prefix = bracket_prefix + ("{" if index == 0 else "")
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


__all__ = ["expand_usage_parts", "wrap_usage_parts", "wrap_visible_words"]

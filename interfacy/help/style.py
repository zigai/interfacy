from typing import Protocol

from stdl.st import TextStyle


class HelpStyle(Protocol):
    """Structural contract for semantic styling of rendered help tokens."""

    type: TextStyle
    type_keyword: TextStyle
    type_bracket: TextStyle
    type_punctuation: TextStyle
    type_operator: TextStyle
    type_literal: TextStyle
    default: TextStyle
    description: TextStyle
    string: TextStyle
    extra_data: TextStyle
    flag_short: TextStyle
    flag_long: TextStyle
    flag_positional: TextStyle
    usage_style: TextStyle | None
    usage_text_style: TextStyle | None
    section_heading_style: TextStyle | None
    placeholder_style: TextStyle | None
    command_name_style: TextStyle | None


__all__ = ["HelpStyle"]

"""Argument row building for help layouts."""

from enum import Enum
from typing import TYPE_CHECKING, Any

from stdl.st import ansi_len, with_style

from interfacy.help.formatting import format_default_for_help, format_type_for_help
from interfacy.help.layouts.columns import format_templated_help_line

if TYPE_CHECKING:  # pragma: no cover
    from interfacy.help.layouts.base import HelpLayout
    from interfacy.help.style import HelpStyle
    from interfacy.schema import Argument

TERMINAL_PUNCTUATION = (".", "?", "!")


def enum_matches(value: Any, member_name: str) -> bool:
    """Return whether ``value`` equals the member ``member_name`` of its own type."""
    member = getattr(type(value), member_name, None)
    return value == member


def is_boolean_argument(arg: "Argument") -> bool:
    """Return whether an argument is rendered as a boolean flag."""
    return enum_matches(arg.value_shape, "FLAG")


def is_option_argument(arg: "Argument") -> bool:
    """Return whether an argument is an option rather than a positional."""
    return enum_matches(arg.kind, "OPTION")


def has_help_default(arg: "Argument") -> bool:
    """Return whether an argument has a default value that help should show."""
    default = arg.argument_default
    return default.appears_in_help and default.value is not None


def is_varargs_positional(arg: "Argument") -> bool:
    """Return whether an argument is a positional that accepts a list of values."""
    return enum_matches(arg.value_shape, "LIST") and not is_option_argument(arg)


def format_choice(value: Any) -> str:
    """Return the help text for one choice value, using enum values where they are strings."""
    if isinstance(value, Enum):
        raw = value.value
        if isinstance(raw, str):
            return raw

        return value.name

    return str(value)


def format_argument_choice(arg: "Argument", value: Any) -> str:
    """Return the help text for one choice of an argument, resolving enum member names."""
    enum_type = arg.type
    if isinstance(value, str) and isinstance(enum_type, type) and issubclass(enum_type, Enum):
        enum_member = enum_type.__members__.get(value)
        if enum_member is not None:
            return format_choice(enum_member)

    return format_choice(value)


def styled_choices(arg: "Argument", style: "HelpStyle") -> str:
    """Return an argument's choices as a comma-separated, styled list."""
    return ", ".join(
        [
            with_style(format_argument_choice(arg, choice), style.string)
            for choice in arg.choices or ()
        ]
    )


def type_for_argument_help(arg: "Argument") -> Any | None:
    """Return the annotation shown for an argument, widened for list and tuple values."""
    if arg.type is None:
        return None

    if enum_matches(arg.value_shape, "LIST"):
        try:
            return list[arg.type]
        except TypeError:
            return arg.type

    if enum_matches(arg.value_shape, "TUPLE") and arg.cardinality.group_size > 1:
        try:
            return tuple.__class_getitem__(tuple([arg.type] * arg.cardinality.group_size))
        except TypeError:
            return arg.type

    return arg.type


def format_bool_default(value: Any) -> str:
    """Return ``true`` or ``false`` for a boolean default."""
    return "true" if bool(value) else "false"


def suppress_false_default_for_positive_boolean_flag(default_text: str, *, long_flag: str) -> str:
    """
    Hide a ``false`` default when the flag itself reads as the positive form.

    Args:
        default_text (str): Rendered default value.
        long_flag (str): Long flag shown for the boolean option.
    """
    if default_text.lower() != "false":
        return default_text
    if long_flag.startswith("--") and not long_flag.startswith("--no-"):
        return ""

    return default_text


def boolean_default_value(arg: "Argument") -> Any:
    """Return the value a boolean flag defaults to for help display."""
    if arg.boolean_behavior is not None:
        return arg.boolean_behavior.default
    if has_help_default(arg):
        return arg.argument_default.value

    return False


def help_default_text(arg: "Argument", *, long_flag: str) -> str:
    """
    Return the unstyled text shown in an argument's default column.

    Args:
        arg (Argument): Argument schema to inspect.
        long_flag (str): Long flag shown for boolean options.
    """
    if is_boolean_argument(arg):
        if arg.is_help_action:
            return ""

        return suppress_false_default_for_positive_boolean_flag(
            format_bool_default(boolean_default_value(arg)),
            long_flag=long_flag,
        )

    if not arg.required and has_help_default(arg):
        return format_default_for_help(arg.argument_default.value)

    return ""


def default_column_texts(arguments: list["Argument"]) -> list[str]:
    """Return the default-column text of every argument in one help section."""
    return [
        help_default_text(argument, long_flag=primary_boolean_flag(argument))
        for argument in arguments
    ]


def primary_boolean_flag(arg: "Argument") -> str:
    """Return the first long flag a boolean option exposes, or its first flag."""
    behavior = arg.boolean_behavior
    exposed_flags = (
        (*behavior.positive_flags, *behavior.negative_flags) if behavior is not None else arg.flags
    )
    longs = [flag for flag in exposed_flags if flag.startswith("--")]
    if not longs:
        return exposed_flags[0] if exposed_flags else ""

    return longs[0]


def argument_metavar(arg: "Argument") -> str:
    """Return the upper-case metavar shown for an argument."""
    return (arg.metavar or arg.display_name or arg.name or "value").upper()


def build_flag_parts(
    arg: "Argument",
    *,
    include_metavar: bool,
) -> tuple[str, str, str, bool]:
    """
    Build the flag texts shown for an argument.

    Args:
        arg (Argument): Argument schema to render.
        include_metavar (bool): Append the metavar to value-taking option flags.

    Returns:
        tuple[str, str, str, bool]: Joined flag text, short flag text, long flag text, and
        whether the argument is an option.
    """
    exposed_flags = arg.flags
    if arg.boolean_behavior is not None:
        exposed_flags = (
            *arg.boolean_behavior.positive_flags,
            *arg.boolean_behavior.negative_flags,
        )

    shorts = [f for f in exposed_flags if f.startswith("-") and not f.startswith("--")]
    longs = [f for f in exposed_flags if f.startswith("--")]
    is_option = is_option_argument(arg)
    is_bool = is_boolean_argument(arg)

    if is_bool:
        flag_short = ", ".join(shorts)
        flag_long = ", ".join(longs)
        joined = ", ".join(flag for flag in (flag_short, flag_long) if flag)

        return joined, flag_short, flag_long, is_option

    metavar = ""
    needs_value = arg.type is not None
    repeated_metavar = " ".join([argument_metavar(arg)] * max(arg.cardinality.group_size, 1))
    if not is_option or (needs_value and include_metavar):
        metavar = repeated_metavar

    def with_metavar(flag: str) -> str:
        return f"{flag} {metavar}" if metavar else flag

    flag_short = with_metavar(shorts[0]) if shorts else ""
    flag_long = with_metavar(longs[0]) if longs else ""

    if is_option:
        joined = ", ".join([p for p in (flag_short, flag_long) if p])
    else:
        joined = metavar or (arg.name or "")

    return joined, flag_short, flag_long, is_option


def adaptive_argument_flag(layout: "HelpLayout", arg: "Argument") -> str:
    """Return the flag column text for an adaptive-layout row."""
    flag, flag_short, flag_long, is_option = layout._build_flag_parts_from_argument(arg)
    if is_option and flag_short and flag_long and layout.include_metavar_in_flag_display:
        return f"{flag_short.split(' ', 1)[0]}, {flag_long}"

    return flag


def build_styled_columns(
    layout: "HelpLayout",
    flag_short: str,
    flag_long: str,
    flag: str,
    *,
    is_option: bool,
    pos_width: int,
) -> dict[str, str]:
    """
    Build styled flag strings padded to their columns by visible width.

    Args:
        layout (HelpLayout): Layout providing flag styles and column widths.
        flag_short (str): Short flag text.
        flag_long (str): Long flag text.
        flag (str): Joined flag text.
        is_option (bool): Whether the argument is an option.
        pos_width (int): Width of the combined flag column.
    """
    style = layout.style
    short_styled = layout._style_flag_token(flag_short, style.flag_short) if flag_short else ""
    long_styled = layout._style_flag_token(flag_long, style.flag_long) if flag_long else ""

    if not is_option and flag:
        flag_styled = layout._style_flag_token(flag, style.flag_positional)
    else:
        styled_parts = [part for part in (short_styled, long_styled) if part]
        flag_styled = ", ".join(styled_parts) if styled_parts else flag

    return {
        "flag_short_styled": short_styled,
        "flag_long_styled": long_styled,
        "flag_styled": flag_styled,
        "flag_short_col": pad_visible(short_styled, layout.short_flag_width),
        "flag_long_col": pad_visible(long_styled, layout.long_flag_width),
        "flag_col": pad_visible(flag_styled if flag else "", pos_width),
    }


def pad_visible(text: str, width: int) -> str:
    """Right-pad text to ``width`` visible columns, ignoring ANSI sequences."""
    return f"{text}{' ' * max(0, width - ansi_len(text))}"


def build_extra(layout: "HelpLayout", arg: "Argument") -> str:
    """
    Build the bracketed type, choices, and default metadata for an argument.

    Args:
        layout (HelpLayout): Layout providing labels and styles.
        arg (Argument): Argument schema to render.
    """
    style = layout.style
    parts: list[str] = []
    default_added = False
    is_bool = is_boolean_argument(arg)
    shows_default = not arg.required and has_help_default(arg)

    if arg.type is not None and not is_bool:
        if arg.choices:
            param_info = layout.prefix_choices + styled_choices(arg, style)
            if shows_default:
                default_text = layout.prefix_default + with_style(
                    format_default_for_help(arg.argument_default.value), style.default
                )
                param_info += ", " + default_text
                default_added = True
        else:
            type_str = format_type_for_help(type_for_argument_help(arg), style.type, theme=style)
            param_info = layout.prefix_type + type_str
        parts.append(param_info)

    if shows_default and not is_bool and not default_added:
        parts.append(", ")
        parts.append(
            layout.prefix_default
            + with_style(format_default_for_help(arg.argument_default.value), style.default)
        )

    if not parts:
        return ""

    return f"[{''.join(parts)}]"


def build_argument_values(layout: "HelpLayout", arg: "Argument") -> dict[str, str]:
    """
    Build the template values for one argument row.

    Args:
        layout (HelpLayout): Layout providing flag, extra, and column hooks.
        arg (Argument): Argument schema to render.
    """
    style = layout.style
    flag, flag_short, flag_long, is_option = layout._build_flag_parts_from_argument(arg)

    is_bool = is_boolean_argument(arg)
    description = layout._format_doc_text(arg.help or "")
    if description and not description.endswith(TERMINAL_PUNCTUATION) and is_bool:
        description += "."

    description = with_style(description, style.description)

    default_raw = help_default_text(arg, long_flag=flag_long)
    styled_default = with_style(default_raw, style.default) if default_raw else ""
    pad = max(0, layout.default_field_width - ansi_len(styled_default))

    choices_str = styled_choices(arg, style) if arg.choices else ""
    choices_label = "choices:" if choices_str else ""
    choices_block = f" [{choices_label} {choices_str}]" if choices_str else ""

    arg_type_for_help = type_for_argument_help(arg)
    type_str = ""
    if arg_type_for_help is not None and not is_bool and not arg.choices:
        type_str = format_type_for_help(arg_type_for_help, style.type, theme=style)

    is_varargs = enum_matches(arg.value_shape, "LIST") and not is_option
    is_required = arg.required and not is_varargs

    values: dict[str, str] = {
        "flag": flag,
        "flag_short": flag_short,
        "flag_long": flag_long,
        "description": description,
        "type": type_str,
        "default": styled_default,
        "default_padded": f"{' ' * pad}{styled_default}",
        "choices": choices_str,
        "choices_label": choices_label,
        "choices_block": choices_block,
        "extra": layout._build_extra_from_argument(arg),
        "required": layout.required_indicator if is_required else "",
        "metavar": argument_metavar(arg),
    }

    values.update(layout._build_styled_columns(flag_short, flag_long, flag, is_option))

    return values


def format_argument_text(layout: "HelpLayout", arg: "Argument") -> str:
    """
    Render argument help text without a column template.

    Args:
        layout (HelpLayout): Layout providing labels, styles, and the extra hook.
        arg (Argument): Argument schema to render.
    """
    if arg.required and arg.type is None:
        return ""

    style = layout.style
    parts: list[str] = []
    if is_boolean_argument(arg):
        if arg.help:
            description = layout._format_doc_text(arg.help)
            if not description.endswith(TERMINAL_PUNCTUATION):
                description += "."
            parts.append(with_style(description, style.description))
    else:
        if arg.help:
            parts.append(f"{with_style(layout._format_doc_text(arg.help), style.description)} ")

        parts.append(layout._build_extra_from_argument(arg))

    text = "".join(parts)
    if not arg.required:
        return text
    if layout.required_indicator_pos == "left":
        return f"{layout.required_indicator} {text}"

    return f"{text} {layout.required_indicator}"


def format_argument_row(layout: "HelpLayout", arg: "Argument", indent: int) -> str:
    """
    Render one argument using the layout's option or positional template.

    Args:
        layout (HelpLayout): Layout providing templates and row hooks.
        arg (Argument): Argument schema to render.
        indent (int): Leading indent width in spaces.
    """
    template = layout.format_option if is_option_argument(arg) else layout.format_positional
    if not template:
        return format_argument_text(layout, arg)

    return format_templated_help_line(
        layout,
        template=template,
        values=layout._build_values_from_argument(arg),
        raw_description=layout._format_doc_text(arg.help or ""),
        indent=indent,
        is_required=arg.required and not is_varargs_positional(arg),
        is_help_option=arg.is_help_action,
    )


__all__ = [
    "adaptive_argument_flag",
    "argument_metavar",
    "boolean_default_value",
    "build_argument_values",
    "build_extra",
    "build_flag_parts",
    "build_styled_columns",
    "default_column_texts",
    "enum_matches",
    "format_argument_choice",
    "format_argument_row",
    "format_argument_text",
    "format_bool_default",
    "format_choice",
    "has_help_default",
    "help_default_text",
    "is_boolean_argument",
    "is_option_argument",
    "is_varargs_positional",
    "pad_visible",
    "primary_boolean_flag",
    "styled_choices",
    "suppress_false_default_for_positive_boolean_flag",
    "type_for_argument_help",
]

"""Template column engine, overflow wrapping, and field widths for help layouts."""

import re
from typing import TYPE_CHECKING

from stdl.st import ansi_len, with_style

from interfacy.help.wrapping import wrap_overwide_line, wrap_plain_words

if TYPE_CHECKING:  # pragma: no cover
    from interfacy.help.layouts.base import HelpLayout
    from interfacy.schema import Argument

DESCRIPTION_MARKER = "<<__DESC__>>"
DEFAULT_ADAPTIVE_HELP_POSITION = 32


def safe_template_format(template: str, values: dict[str, str]) -> str | None:
    """Format a help template, returning None when the values do not satisfy it."""
    try:
        return template.format(**values)
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def probe_template_field_index(
    *,
    template: str,
    values: dict[str, str],
    field_name: str,
    marker: str,
) -> tuple[str, int]:
    """
    Render a template with a marker in one field and locate that marker.

    Args:
        template (str): Help line template.
        values (dict[str, str]): Template values.
        field_name (str): Field replaced by the marker.
        marker (str): Unique text substituted into the field.

    Returns:
        tuple[str, int]: The probe render and the marker offset, or ``("", -1)`` when the
        template cannot be rendered.
    """
    probe_values = dict(values)
    probe_values[field_name] = marker
    probe_render = safe_template_format(template, probe_values)
    if probe_render is None:
        return "", -1

    return probe_render, probe_render.find(marker)


def template_probe_values(layout: "HelpLayout") -> dict[str, str]:
    """Return blank template values sized to the layout's configured columns."""
    values = {
        "flag": "",
        "flag_short": "",
        "flag_long": "",
        "flag_short_col": " " * layout.short_flag_width,
        "flag_long_col": " " * layout.long_flag_width,
        "flag_col": " " * layout.pos_flag_width,
        "description": "",
        "type": "",
        "default": "",
        "default_padded": " " * layout.default_field_width,
        "choices": "",
        "choices_label": "",
        "choices_block": "",
        "extra": "",
        "details": "",
        "required": "",
        "metavar": "",
    }
    if hasattr(layout, "column_gap"):
        values["column_gap"] = layout.column_gap

    return values


def template_token_index(layout: "HelpLayout", field_name: str) -> int | None:
    """
    Return the column where a template field starts, if the layout uses templates.

    Args:
        layout (HelpLayout): Layout whose option or positional template is probed.
        field_name (str): Template field to locate.
    """
    if not layout._use_template_layout():
        return None

    template = layout.format_option or layout.format_positional
    if not template:
        return None

    marker = f"<<__{field_name}__>>"
    values = template_probe_values(layout)
    values[field_name] = marker
    probe_render = safe_template_format(template, values)
    if probe_render is None:
        return None

    marker_idx = probe_render.find(marker)
    if marker_idx == -1:
        return None

    if field_name == "default_padded" and marker_idx > 0 and probe_render[marker_idx - 1] == "[":
        return marker_idx - 1

    return marker_idx


def prepare_default_overflow(
    layout: "HelpLayout",
    *,
    template: str,
    values: dict[str, str],
) -> tuple[str, bool]:
    """
    Handle a default value wider than the default column.

    Args:
        layout (HelpLayout): Layout providing the default column policy.
        template (str): Help line template.
        values (dict[str, str]): Template values, updated in place.

    Returns:
        tuple[str, bool]: Default text to render on an overflow line, and whether description
        wrapping should be skipped.
    """
    if "{default_padded}" not in template:
        return "", False

    styled_default = values.get("default", "")
    if not styled_default or ansi_len(styled_default) <= layout.default_field_width:
        return "", False

    if layout.default_overflow_mode == "inline":
        values["default"] = styled_default
        values["default_padded"] = styled_default

        return "", True

    values["default"] = ""
    values["default_padded"] = " " * layout.default_field_width

    return styled_default, False


def apply_description_wrapping(
    layout: "HelpLayout",
    *,
    template: str,
    values: dict[str, str],
    raw_description: str,
    indent: int,
    skip_wrap: bool,
    default_overflow: str,
) -> None:
    """
    Wrap the description field so continuation lines align under its column.

    Args:
        layout (HelpLayout): Layout providing terminal width and styles.
        template (str): Help line template.
        values (dict[str, str]): Template values, updated in place.
        raw_description (str): Unstyled description text.
        indent (int): Leading indent of the rendered row.
        skip_wrap (bool): Keep the description on one line.
        default_overflow (str): Default text to append on its own line.
    """
    probe_render, marker_idx = probe_template_field_index(
        template=template,
        values=values,
        field_name="description",
        marker=DESCRIPTION_MARKER,
    )
    if marker_idx == -1:
        return

    style = layout.style
    prefix_width = ansi_len(probe_render[:marker_idx])
    cont_indent = " " * prefix_width
    wrap_width = max(10, layout._terminal_width() - indent - prefix_width - 4)
    wrapped = wrap_plain_words(raw_description, wrap_width)

    if wrapped and not skip_wrap:
        styled_lines = [with_style(wrapped[0], style.description)]
        styled_lines.extend(
            cont_indent + with_style(line, style.description) for line in wrapped[1:]
        )
        values["description"] = "\n".join(styled_lines)

    if default_overflow:
        arrow = with_style("→", style.extra_data)
        label = with_style("default:", style.extra_data)
        overflow_line = f"{arrow} {label} {default_overflow}"
        if values["description"]:
            values["description"] = f"{values['description']}\n{cont_indent}{overflow_line}"
        else:
            values["description"] = f"\n{cont_indent}{overflow_line}"


def wrap_template_field_value(
    *,
    template: str,
    values: dict[str, str],
    field_name: str,
    indent: int,
    terminal_width: int,
) -> str | None:
    """
    Wrap one single-line template field that would overflow the terminal.

    Args:
        template (str): Help line template.
        values (dict[str, str]): Template values.
        field_name (str): Field to wrap.
        indent (int): Leading indent of the rendered row.
        terminal_width (int): Terminal width in columns.

    Returns:
        str | None: The wrapped value, or None when the field fits or cannot be located.
    """
    raw_value = values.get(field_name, "")
    if not raw_value or "\n" in raw_value:
        return None

    marker = f"<<__{field_name.upper()}__>>"
    probe_render, marker_idx = probe_template_field_index(
        template=template,
        values=values,
        field_name=field_name,
        marker=marker,
    )
    if marker_idx == -1:
        return None

    prefix_width = ansi_len(probe_render[:marker_idx])
    wrap_width = max(10, terminal_width - indent - prefix_width - 4)
    normalized = " ".join(raw_value.split())
    if ansi_len(normalized) <= wrap_width:
        return None

    wrapped: list[str] = []
    for word in normalized.split():
        if not wrapped:
            wrapped.append(word)
        elif ansi_len(wrapped[-1]) + 1 + ansi_len(word) <= wrap_width:
            wrapped[-1] = f"{wrapped[-1]} {word}"
        else:
            wrapped.append(word)

    if len(wrapped) <= 1:
        return None

    cont_indent = " " * (prefix_width + indent)

    return wrapped[0] + "".join(f"\n{cont_indent}{line}" for line in wrapped[1:])


def template_fallback_line(values: dict[str, str]) -> str:
    """Render a row without the template when the template cannot be formatted."""
    return f"{values['flag']:<40} {values['description']} {values.get('extra', '')}"


def collapse_empty_default_slot(
    layout: "HelpLayout",
    rendered: str,
    template: str,
    default_value: str,
    *,
    is_help_option: bool = False,
) -> str:
    """
    Remove the empty ``[ ]`` default slot from a rendered row when the layout asks for it.

    Args:
        layout (HelpLayout): Layout providing the empty-slot policy.
        rendered (str): Rendered help row.
        template (str): Help line template.
        default_value (str): Rendered default value for the row.
        is_help_option (bool): Whether the row is the synthetic help option.
    """
    if not layout.suppress_empty_default_brackets_for_help:
        return rendered
    if "{default_padded}" not in template or default_value:
        return rendered

    match = re.search(r"\[\s*\]\s*", rendered)
    if match is None:
        return rendered

    prefix = rendered[: match.start()]
    suffix = rendered[match.end() :]
    removed_width = match.end() - match.start()

    if is_help_option and layout.keep_empty_default_slot_for_help:
        return f"{prefix}{' ' * removed_width}{suffix}"

    needs_separator = (
        bool(prefix) and bool(suffix) and not prefix[-1].isspace() and not suffix[0].isspace()
    )
    separator = " " if needs_separator else ""
    collapsed = f"{prefix}{separator}{suffix}"
    if "\n" not in collapsed:
        return collapsed

    shift = max(0, removed_width - len(separator))
    lines = collapsed.splitlines()
    shifted = [lines[0]]
    for line in lines[1:]:
        leading = len(line) - len(line.lstrip(" "))
        shifted.append(line[min(shift, leading) :])

    return "\n".join(shifted)


def finalize_templated_line(
    layout: "HelpLayout",
    *,
    rendered: str,
    template: str,
    values: dict[str, str],
    is_required: bool,
    indent: int,
    is_help_option: bool = False,
) -> str:
    """
    Apply required markers, empty-slot cleanup, and overflow wrapping to a rendered row.

    Args:
        layout (HelpLayout): Layout providing the slot policy and terminal width.
        rendered (str): Row rendered from the template.
        template (str): Help line template.
        values (dict[str, str]): Template values used for the row.
        is_required (bool): Whether the row is for a required argument.
        indent (int): Leading indent of the rendered row.
        is_help_option (bool): Whether the row is the synthetic help option.
    """
    if is_required and values.get("required") and values["required"] not in rendered:
        rendered = f"{rendered} {values['required']}"

    if "[type:" in rendered and "type" in values and not values["type"]:
        rendered = re.sub(r" ?\[type:\s*\]", "", rendered)

    rendered = collapse_empty_default_slot(
        layout,
        rendered,
        template,
        values.get("default", ""),
        is_help_option=is_help_option,
    )

    return wrap_overwide_line(
        rendered.rstrip(),
        terminal_width=layout._terminal_width(),
        indent=indent,
    )


def format_templated_help_line(
    layout: "HelpLayout",
    *,
    template: str,
    values: dict[str, str],
    raw_description: str,
    indent: int,
    is_required: bool,
    is_help_option: bool = False,
) -> str:
    """
    Render one argument row from a column template.

    Args:
        layout (HelpLayout): Layout providing column policy, styles, and terminal width.
        template (str): Help line template.
        values (dict[str, str]): Template values, updated in place while wrapping.
        raw_description (str): Unstyled description text.
        indent (int): Leading indent of the rendered row.
        is_required (bool): Whether the row is for a required argument.
        is_help_option (bool): Whether the row is the synthetic help option.
    """
    default_overflow, skip_wrap = prepare_default_overflow(
        layout,
        template=template,
        values=values,
    )
    apply_description_wrapping(
        layout,
        template=template,
        values=values,
        raw_description=raw_description,
        indent=indent,
        skip_wrap=skip_wrap,
        default_overflow=default_overflow,
    )

    if not raw_description.strip():
        wrapped_extra = wrap_template_field_value(
            template=template,
            values=values,
            field_name="extra",
            indent=indent,
            terminal_width=layout._terminal_width(),
        )
        if wrapped_extra is not None:
            values["extra"] = wrapped_extra

    rendered = safe_template_format(template, values)
    if rendered is None:
        rendered = template_fallback_line(values)

    return finalize_templated_line(
        layout,
        rendered=rendered,
        template=template,
        values=values,
        is_required=is_required,
        indent=indent,
        is_help_option=is_help_option,
    )


def format_adaptive_row(
    flag: str,
    help_text: str,
    *,
    help_position: int | None,
    terminal_width: int,
) -> str:
    """
    Render an adaptive-layout row with the help text starting at the help column.

    Args:
        flag (str): Flag or name column text.
        help_text (str): Rendered help text for the argument.
        help_position (int | None): Column where help text starts.
        terminal_width (int): Terminal width in columns.
    """
    if not help_text:
        return flag

    position = help_position if isinstance(help_position, int) else DEFAULT_ADAPTIVE_HELP_POSITION
    gap = max(2, position - ansi_len(flag))
    rendered = f"{flag}{' ' * gap}{help_text}"

    return wrap_overwide_line(rendered, terminal_width=terminal_width, indent=2)


def compute_default_field_width(
    max_len: int,
    *,
    base_width: int,
    terminal_width: int,
    term_ratio: int,
    width_max: int | None,
) -> int:
    """
    Size the default column to fit ``max_len`` within terminal-derived bounds.

    Args:
        max_len (int): Widest default value in the section.
        base_width (int): Configured minimum default column width.
        terminal_width (int): Terminal width in columns.
        term_ratio (int): Fraction of the terminal width the column may use.
        width_max (int | None): Absolute maximum column width.
    """
    term_cap = max(base_width, terminal_width // max(1, term_ratio))
    if width_max is not None:
        term_cap = min(term_cap, width_max)

    return max(base_width, min(max_len, term_cap))


def flag_column_width(
    layout: "HelpLayout",
    arguments: list["Argument"],
    *,
    template: str,
    base_width: int,
) -> int:
    """
    Return the flag column width needed for a section of argument rows.

    Args:
        layout (HelpLayout): Layout that builds the flag text.
        arguments (list[Argument]): Arguments rendered in one help section.
        template (str): Help line template.
        base_width (int): Configured minimum flag column width.
    """
    if "{flag_col}" not in template:
        return base_width

    max_flag_len = 0
    for argument in arguments:
        flag, _, _, _ = layout._build_flag_parts_from_argument(argument)
        max_flag_len = max(max_flag_len, ansi_len(flag))

    return max(base_width, max_flag_len)


__all__ = [
    "apply_description_wrapping",
    "collapse_empty_default_slot",
    "compute_default_field_width",
    "finalize_templated_line",
    "flag_column_width",
    "format_adaptive_row",
    "format_templated_help_line",
    "prepare_default_overflow",
    "probe_template_field_index",
    "safe_template_format",
    "template_fallback_line",
    "template_probe_values",
    "template_token_index",
    "wrap_template_field_value",
]

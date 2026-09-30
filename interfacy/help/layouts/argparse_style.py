import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from interfacy.help.colors import NoColor
from interfacy.help.formatting import format_default_for_help
from interfacy.help.layouts.base import HelpLayout
from interfacy.help.style import HelpStyle

if TYPE_CHECKING:  # pragma: no cover
    from interfacy.schema import Argument


@dataclass(kw_only=True)
class ArgparseLayout(HelpLayout):
    """Layout that follows the default ``argparse`` help output."""

    style: HelpStyle = field(default_factory=NoColor)

    include_metavar_in_flag_display: bool = True
    required_indicator: str = ""
    clear_metavar: bool = False

    help_position: int | None = 24
    layout_mode: Literal["auto", "adaptive", "template"] = "adaptive"
    parser_command_usage_suffix: str = "{command}"

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _collapse_duplicate_terminal_period(text: str) -> str:
        if not text:
            return text

        stripped = text.rstrip()
        trailing_ws = text[len(stripped) :]

        if stripped.endswith("..") and not stripped.endswith("..."):
            stripped = stripped[:-1]

        return stripped + trailing_ws

    @classmethod
    def _description_mentions_same_default(cls, description: str, default_text: str) -> bool:
        if not description or not default_text:
            return False

        normalized_description = cls._normalize_whitespace(description).lower()
        normalized_default = cls._normalize_whitespace(default_text).lower()
        if not normalized_default:
            return False

        return (
            f"defaults to {normalized_default}" in normalized_description
            or f"default: {normalized_default}" in normalized_description
        )

    @classmethod
    def _description_mentions_same_choices(
        cls,
        description: str,
        choices_text: str,
    ) -> bool:
        if not description or not choices_text:
            return False

        normalized_description = cls._normalize_whitespace(description).lower()
        normalized_choices = cls._normalize_whitespace(choices_text).lower()
        return (
            f"choices: {normalized_choices}" in normalized_description
            or f"possible values: {normalized_choices}" in normalized_description
        )

    @classmethod
    def _append_sentence(cls, description: str, sentence: str) -> str:
        if not sentence:
            return description

        description = cls._collapse_duplicate_terminal_period(description)

        separator = ""
        if description:
            separator = " " if description.rstrip().endswith((".", "?", "!", ":", ";")) else ". "

        terminal = "" if sentence.endswith((".", "?", "!", ":", ";")) else "."

        return f"{description}{separator}{sentence}{terminal}"

    @classmethod
    def _with_default_sentence(cls, description: str, has_default: bool, default: Any) -> str:
        if not has_default:
            return description

        default_text = format_default_for_help(default)
        if default_text in {"", '""'}:
            default_text = "''"

        if cls._description_mentions_same_default(description, default_text):
            return description

        return cls._append_sentence(description, f"Defaults to {default_text}")

    @classmethod
    def _with_choices_sentence(
        cls,
        description: str,
        choices: Sequence[Any] | None,
    ) -> str:
        if not choices:
            return description

        choices_text = ", ".join(str(choice) for choice in choices)
        if cls._description_mentions_same_choices(description, choices_text):
            return description

        return cls._append_sentence(description, f"Choices: {choices_text}")

    def format_argument(
        self,
        arg: "Argument",
        indent: int = 2,  # noqa: ARG002 - API compatibility
    ) -> str:
        description = self.format_description(arg.help or "")
        has_default = (
            not arg.required
            and arg.argument_default.appears_in_help
            and arg.argument_default.value is not None
        )
        default_value = arg.argument_default.value
        if has_default and self._arg_is_bool(arg):
            if arg.boolean_behavior is not None:
                default_value = arg.boolean_behavior.default
            rendered_default = self._format_bool_default_for_help(default_value)
            has_default = bool(
                self._suppress_false_default_for_positive_boolean_flag(
                    rendered_default,
                    long_flag=self._get_primary_boolean_flag_from_argument(arg),
                )
            )
        description = self._with_default_sentence(description, has_default, default_value)
        choices = (
            [self._format_argument_choice_for_help(arg, choice) for choice in arg.choices]
            if arg.choices
            else None
        )

        return self._with_choices_sentence(description, choices)


__all__ = [
    "ArgparseLayout",
]

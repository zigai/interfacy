import pytest

from interfacy import Interfacy
from interfacy.exceptions import UsageError
from tests.fixtures.classes import Math
from tests.fixtures.commands import (
    fn_literal_arg,
    pow,
)


class TestPowFunctionParsing:
    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_kw_only_abbrev_collision_skips_second_short(self, parser: Interfacy):
        """Verify that short-flag collisions do not fall back to multi-character aliases."""

        def fn_collision(*, value: int = 1, version: int = 2) -> tuple[int, int]:
            return value, version

        parser.add_command(fn_collision)
        args = parser.parse_args(["-v", "3", "--version", "4"])
        assert args == {"value": 3, "version": 4}


class TestMathClassParsing:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_from_class(self, parser: Interfacy):
        """Verify parsing of commands derived from class methods and init parameters."""
        parser.add_command(Math)
        args = parser.parse_args(["pow", "2", "-e", "2"])

        assert args == {
            "command": "pow",
            "rounding": 6,
            "pow": {
                "base": 2,
                "exponent": 2,
            },
        }

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_class_initializer_options_can_follow_subcommand(self, parser: Interfacy):
        """Verify class initializer options are accepted after method arguments."""
        parser.add_command(Math)
        args = parser.parse_args(["pow", "2", "-e", "2", "--rounding", "3"])

        assert args == {
            "command": "pow",
            "rounding": 3,
            "pow": {
                "base": 2,
                "exponent": 2,
            },
        }

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_subcommand_option_takes_precedence_over_initializer_option(
        self,
        parser: Interfacy,
    ):
        """Verify options after a subcommand stay on the nearest command that accepts them."""

        class ModeTool:
            def __init__(self, mode: str = "parent") -> None:
                self.mode = mode

            def run(self, mode: str = "child") -> tuple[str, str]:
                return self.mode, mode

        parser.add_command(ModeTool)
        args = parser.parse_args(["run", "--mode", "leaf"])

        assert args == {
            "command": "run",
            "mode": "parent",
            "run": {"mode": "leaf"},
        }

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_initializer_option_after_subcommand_supports_equals_form(
        self,
        parser: Interfacy,
    ):
        """Verify late initializer options support --option=value syntax."""
        parser.add_command(Math)
        args = parser.parse_args(["pow", "2", "--rounding=3"])

        assert args == {
            "command": "pow",
            "rounding": 3,
            "pow": {
                "base": 2,
                "exponent": 2,
            },
        }

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_initializer_negative_boolean_option_can_follow_subcommand(
        self,
        parser: Interfacy,
    ):
        """Verify late initializer options include generated negative boolean aliases."""

        class ToggleTool:
            def __init__(self, enabled: bool = True) -> None:
                self.enabled = enabled

            def run(self) -> bool:
                return self.enabled

        parser.add_command(ToggleTool)
        args = parser.parse_args(["run", "--no-enabled"])

        assert args == {
            "command": "run",
            "enabled": False,
            "run": {},
        }

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_late_initializer_list_option_stops_before_subcommand_option(
        self,
        parser: Interfacy,
    ):
        """Verify variable-length initializer options do not consume child options."""

        class TagsTool:
            def __init__(self, tags: list[str] | None = None) -> None:
                self.tags = tags

            def run(self, count: int = 1) -> tuple[list[str] | None, int]:
                return self.tags, count

        parser.add_command(TagsTool)
        args = parser.parse_args(["run", "--tags", "a", "b", "--count", "2"])

        assert args == {
            "command": "run",
            "tags": ["a", "b"],
            "run": {"count": 2},
        }

    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_required_late_initializer_list_option_is_applied(
        self,
        parser: Interfacy,
    ):
        """Verify required late list initializer options are applied after parsing."""

        class TagsTool:
            def __init__(self, *, tags: list[str]) -> None:
                self.tags = tags

            def run(self) -> list[str]:
                return self.tags

        parser.add_command(TagsTool)
        args = parser.parse_args(["run", "--tags", "a"])

        assert args == {
            "command": "run",
            "tags": ["a"],
            "run": {},
        }

    @pytest.mark.parametrize("parser", ["argparse_kw_only"], indirect=True)
    def test_typed_late_initializer_list_option_parse_error_uses_argparse(
        self,
        parser: Interfacy,
    ):
        """Verify late list conversion errors use argparse parse handling."""

        class TagsTool:
            def __init__(self, *, tags: list[int] | None = None) -> None:
                self.tags = tags

            def run(self) -> list[int] | None:
                return self.tags

        parser.add_command(TagsTool)

        with pytest.raises(UsageError):
            parser.parse_args(["run", "--tags", "bad"])

    @pytest.mark.parametrize("parser", ["click_kw_only"], indirect=True)
    def test_typed_late_initializer_list_option_parse_error_uses_click(
        self,
        parser: Interfacy,
    ):
        """Verify late list conversion errors use the public usage-error contract."""
        pytest.importorskip("click")

        class TagsTool:
            def __init__(self, *, tags: list[int] | None = None) -> None:
                self.tags = tags

            def run(self) -> list[int] | None:
                return self.tags

        parser.add_command(TagsTool)

        with pytest.raises(UsageError):
            parser.parse_args(["run", "--tags", "bad"])

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_from_instance(self, parser: Interfacy):
        """Verify parsing of commands derived from instance methods."""
        math = Math(rounding=2)
        parser.add_command(math)  # type: ignore[arg-type]

        args = parser.parse_args(["pow", "2", "-e", "2"])
        assert args == {
            "command": "pow",
            "pow": {
                "base": 2,
                "exponent": 2,
            },
        }


class TestMultipleCommands:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_from_multiple(self, parser: Interfacy):
        """Verify parsing when multiple commands are registered (subcommand routing)."""
        parser.add_command(pow)
        parser.add_command(Math)

        args = parser.parse_args(["pow", "2", "-e", "2"])
        assert args == {
            "command": "pow",
            "pow": {
                "base": 2,
                "exponent": 2,
            },
        }

        args = parser.parse_args(["math", "pow", "2", "-e", "2"])
        assert args == {
            "command": "math",
            "math": {
                "command": "pow",
                "rounding": 6,
                "pow": {
                    "base": 2,
                    "exponent": 2,
                },
            },
        }

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_nested_class_initializer_options_can_follow_subcommand(
        self,
        parser: Interfacy,
    ):
        """Verify nested class initializer options are accepted after method arguments."""
        parser.add_command(pow)
        parser.add_command(Math)

        args = parser.parse_args(["math", "pow", "2", "-e", "2", "--rounding", "3"])
        assert args == {
            "command": "math",
            "math": {
                "command": "pow",
                "rounding": 3,
                "pow": {
                    "base": 2,
                    "exponent": 2,
                },
            },
        }


class TestLiterals:
    @pytest.mark.parametrize("parser", ["argparse_kw_only", "click_kw_only"], indirect=True)
    def test_literal_kwarg(self, parser: Interfacy):
        """Verify parsing of Literal arguments from flag input."""
        parser.add_command(fn_literal_arg)
        args = parser.parse_args(["-c", "RED"])
        assert args["color"] == "RED"

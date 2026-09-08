import pytest

from interfacy import CommandGroup, Interfacy
from tests.fixtures.classes import TextCollector
from tests.fixtures.commands import (
    fn_positional_varargs,
    fn_positional_varargs_kwonly,
    fn_positional_varargs_varkw,
)


class TestMixedPositionalAndVarargs:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_function_with_positional_and_varargs(self, parser: Interfacy):
        """Verify execution of a function with required positional and *args."""
        parser.add_command(fn_positional_varargs)
        assert parser.invoke(args=["primary", "alpha", "beta"]) == (
            "primary",
            ("alpha", "beta"),
        )

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_function_with_positional_and_varargs_omitted(self, parser: Interfacy):
        """Verify execution of a function when *args is omitted."""
        parser.add_command(fn_positional_varargs)
        assert parser.invoke(args=["primary"]) == (
            "primary",
            (),
        )

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_function_with_only_varargs_omitted(self, parser: Interfacy):
        """Verify execution of a function with only *args when omitted."""

        def only_varargs(*paths: str) -> tuple[str, ...]:
            return paths

        parser.add_command(only_varargs)
        assert parser.invoke(args=[]) == ()
        assert parser.invoke(args=["a", "b"]) == ("a", "b")

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_class_method_with_positional_and_varargs(self, parser: Interfacy):
        """Verify execution of class method subcommands with positional + *args."""
        parser.add_command(TextCollector)
        assert parser.invoke(args=["collect", "primary", "alpha", "beta"]) == (
            "primary",
            ("alpha", "beta"),
        )

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_group_function_with_positional_and_varargs(self, parser: Interfacy):
        """Verify grouped command execution with positional + *args."""
        workspace = CommandGroup("workspace")
        workspace.add_command(fn_positional_varargs, name="collect")
        parser.add_command(workspace)
        assert parser.invoke(args=["workspace", "collect", "primary", "alpha", "beta"]) == (
            "primary",
            ("alpha", "beta"),
        )


class TestMixedPositionalVarargsAndKeywordOnly:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_function_with_keyword_only_after_varargs(self, parser: Interfacy):
        """Verify required positional + *args + keyword-only option execution."""
        parser.add_command(fn_positional_varargs_kwonly)
        assert parser.invoke(args=["primary", "alpha", "beta", "--mode", "focused"]) == (
            "primary",
            ("alpha", "beta"),
            "focused",
        )

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_class_method_with_keyword_only_after_varargs(self, parser: Interfacy):
        """Verify class method execution for positional + *args + keyword-only option."""
        parser.add_command(TextCollector)
        assert parser.invoke(
            args=["collect-with-mode", "primary", "alpha", "beta", "--mode", "focused"]
        ) == (
            "primary",
            ("alpha", "beta"),
            "focused",
        )

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_group_function_with_keyword_only_after_varargs(self, parser: Interfacy):
        """Verify grouped command execution for positional + *args + keyword-only option."""
        workspace = CommandGroup("workspace")
        workspace.add_command(fn_positional_varargs_kwonly, name="collect")
        parser.add_command(workspace)
        assert parser.invoke(
            args=["workspace", "collect", "primary", "alpha", "beta", "--mode", "focused"]
        ) == (
            "primary",
            ("alpha", "beta"),
            "focused",
        )


class TestMixedPositionalVarargsAndVarKeyword:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_function_with_var_keyword_after_varargs(self, parser: Interfacy):
        """Verify required positional + *args + **kwargs execution."""
        parser.add_command(fn_positional_varargs_varkw)
        assert parser.invoke(args=["primary", "alpha", '{"mode":"fast","profile":"dev"}']) == (
            "primary",
            ("alpha",),
            {"mode": "fast", "profile": "dev"},
        )

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_class_method_with_var_keyword_after_varargs(self, parser: Interfacy):
        """Verify class method execution for positional + *args + **kwargs."""
        parser.add_command(TextCollector)
        assert parser.invoke(
            args=[
                "collect-with-options",
                "primary",
                "alpha",
                '{"mode":"fast","profile":"dev"}',
            ]
        ) == (
            "primary",
            ("alpha",),
            {"mode": "fast", "profile": "dev"},
        )

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_group_function_with_var_keyword_after_varargs(self, parser: Interfacy):
        """Verify grouped command execution for positional + *args + **kwargs."""
        workspace = CommandGroup("workspace")
        workspace.add_command(fn_positional_varargs_varkw, name="collect")
        parser.add_command(workspace)
        assert parser.invoke(
            args=["workspace", "collect", "primary", "alpha", '{"mode":"fast","profile":"dev"}']
        ) == (
            "primary",
            ("alpha",),
            {"mode": "fast", "profile": "dev"},
        )

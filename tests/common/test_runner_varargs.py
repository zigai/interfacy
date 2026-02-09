import pytest

from interfacy import CommandGroup
from interfacy.core import InterfacyParser
from tests.conftest import (
    TextCollector,
    fn_positional_varargs,
    fn_positional_varargs_kwonly,
    fn_positional_varargs_varkw,
)


class TestMixedPositionalAndVarargs:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_function_with_positional_and_varargs(self, parser: InterfacyParser):
        """Verify execution of a function with required positional and *args."""
        parser.add_command(fn_positional_varargs)
        assert parser.run(args=["primary", "alpha", "beta"]) == (
            "primary",
            ("alpha", "beta"),
        )

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_class_method_with_positional_and_varargs(self, parser: InterfacyParser):
        """Verify execution of class method subcommands with positional + *args."""
        parser.add_command(TextCollector)
        assert parser.run(args=["collect", "primary", "alpha", "beta"]) == (
            "primary",
            ("alpha", "beta"),
        )

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_group_function_with_positional_and_varargs(self, parser: InterfacyParser):
        """Verify grouped command execution with positional + *args."""
        workspace = CommandGroup("workspace")
        workspace.add_command(fn_positional_varargs, name="collect")
        parser.add_command(workspace)
        assert parser.run(args=["workspace", "collect", "primary", "alpha", "beta"]) == (
            "primary",
            ("alpha", "beta"),
        )


class TestMixedPositionalVarargsAndKeywordOnly:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_function_with_keyword_only_after_varargs(self, parser: InterfacyParser):
        """Verify required positional + *args + keyword-only option execution."""
        parser.add_command(fn_positional_varargs_kwonly)
        assert parser.run(args=["primary", "alpha", "beta", "--mode", "focused"]) == (
            "primary",
            ("alpha", "beta"),
            "focused",
        )

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_class_method_with_keyword_only_after_varargs(self, parser: InterfacyParser):
        """Verify class method execution for positional + *args + keyword-only option."""
        parser.add_command(TextCollector)
        assert parser.run(
            args=["collect-with-mode", "primary", "alpha", "beta", "--mode", "focused"]
        ) == (
            "primary",
            ("alpha", "beta"),
            "focused",
        )

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_group_function_with_keyword_only_after_varargs(self, parser: InterfacyParser):
        """Verify grouped command execution for positional + *args + keyword-only option."""
        workspace = CommandGroup("workspace")
        workspace.add_command(fn_positional_varargs_kwonly, name="collect")
        parser.add_command(workspace)
        assert parser.run(
            args=["workspace", "collect", "primary", "alpha", "beta", "--mode", "focused"]
        ) == (
            "primary",
            ("alpha", "beta"),
            "focused",
        )


class TestMixedPositionalVarargsAndVarKeyword:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_function_with_var_keyword_after_varargs(self, parser: InterfacyParser):
        """Verify required positional + *args + **kwargs execution."""
        parser.add_command(fn_positional_varargs_varkw)
        assert parser.run(args=["primary", "alpha", '{"mode":"fast","profile":"dev"}']) == (
            "primary",
            ("alpha",),
            {"mode": "fast", "profile": "dev"},
        )

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_class_method_with_var_keyword_after_varargs(self, parser: InterfacyParser):
        """Verify class method execution for positional + *args + **kwargs."""
        parser.add_command(TextCollector)
        assert parser.run(
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
    def test_group_function_with_var_keyword_after_varargs(self, parser: InterfacyParser):
        """Verify grouped command execution for positional + *args + **kwargs."""
        workspace = CommandGroup("workspace")
        workspace.add_command(fn_positional_varargs_varkw, name="collect")
        parser.add_command(workspace)
        assert parser.run(
            args=["workspace", "collect", "primary", "alpha", '{"mode":"fast","profile":"dev"}']
        ) == (
            "primary",
            ("alpha",),
            {"mode": "fast", "profile": "dev"},
        )

import inspect
from typing import get_type_hints

import pytest

import interfacy
from interfacy import CommandGroup, Interfacy, Param, appearance
from interfacy.appearance import layouts as appearance_layouts
from interfacy.argparse_backend import Argparser
from interfacy.exceptions import ConfigurationError


def test_interfacy_defaults_to_argparse_backend() -> None:
    parser = Interfacy(sys_exit_enabled=False, print_result=False)

    assert parser.backend == "argparse"
    assert isinstance(parser._parser, Argparser)


def test_interfacy_accepts_explicit_argparse_backend() -> None:
    parser = Interfacy(backend="argparse", sys_exit_enabled=False, print_result=False)

    assert parser.backend == "argparse"
    assert isinstance(parser._parser, Argparser)


def test_interfacy_accepts_click_backend() -> None:
    pytest.importorskip("click")
    from interfacy.click_backend import ClickParser

    parser = Interfacy(backend="click", sys_exit_enabled=False, print_result=False)

    assert parser.backend == "click"
    assert isinstance(parser._parser, ClickParser)


def test_interfacy_init_is_fully_typed_without_variadic_kwargs() -> None:
    parameters = inspect.signature(Interfacy.__init__).parameters.values()

    assert inspect.Parameter.VAR_POSITIONAL not in {param.kind for param in parameters}
    assert inspect.Parameter.VAR_KEYWORD not in {param.kind for param in parameters}


def test_interfacy_facade_hides_backend_specific_parser_construction_helpers() -> None:
    parser = Interfacy(sys_exit_enabled=False)

    for name in (
        "install_tab_completion",
        "parser_from_class",
        "parser_from_command",
        "parser_from_function",
        "parser_from_multiple_commands",
    ):
        assert not hasattr(parser, name)


def test_public_parameter_settings_type_hints_resolve() -> None:
    assert "parameter_settings" in get_type_hints(Interfacy.add_command)
    assert "parameter_settings" in get_type_hints(CommandGroup.add_command)


def test_interfacy_rejects_argparse_only_formatter_for_click_backend() -> None:
    with pytest.raises(ConfigurationError, match="formatter_class is only supported"):
        Interfacy(backend="click", formatter_class=object)


def test_interfacy_runs_with_selected_backend() -> None:
    def greet(name: str) -> str:
        return f"Hello, {name}!"

    parser = Interfacy(sys_exit_enabled=False)

    assert parser.run(greet, args=["Ada"]) == "Hello, Ada!"


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_interfacy_add_command_accepts_parameter_settings(backend: str) -> None:
    if backend == "click":
        pytest.importorskip("click")

    def choose(output_format: str = "text") -> str:
        return output_format

    parser = Interfacy(backend=backend, sys_exit_enabled=False)
    parser.add_command(
        choose,
        parameter_settings={"output_format": Param(long="style", short="s")},
    )

    assert parser.run(args=["--style", "json"]) == "json"


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_interfacy_instance_method_accepts_parameter_settings(backend: str) -> None:
    if backend == "click":
        pytest.importorskip("click")

    class Tool:
        def render(self, output_format: str = "text") -> str:
            return output_format

    parser = Interfacy(backend=backend, sys_exit_enabled=False)
    parser.add_command(
        Tool(),
        parameter_settings={"output_format": Param(long="style", short="s")},
    )

    assert parser.run(args=["render", "--style", "json"]) == "json"


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_command_group_instance_method_accepts_parameter_settings(backend: str) -> None:
    if backend == "click":
        pytest.importorskip("click")

    class Tool:
        def render(self, output_format: str = "text") -> str:
            return output_format

    group = CommandGroup("tools")
    group.add_command(
        Tool(),
        name="tool",
        parameter_settings={"output_format": Param(long="style", short="s")},
    )
    parser = Interfacy(backend=backend, sys_exit_enabled=False)
    parser.add_command(group)

    assert parser.run(args=["tools", "tool", "render", "--style", "json"]) == "json"


def test_interfacy_rejects_unknown_backend() -> None:
    with pytest.raises(ConfigurationError, match="backend must be one of: argparse, click"):
        Interfacy(backend="unknown")


def test_backend_classes_are_not_top_level_exports() -> None:
    assert "Interfacy" in interfacy.__all__
    assert "Param" in interfacy.__all__
    assert "params" in interfacy.__all__
    assert "Argparser" not in interfacy.__all__
    assert "ClickParser" not in interfacy.__all__


def test_appearance_does_not_export_simple_layout_alias() -> None:
    assert "SimpleLayout" not in appearance.__all__
    assert "SimpleLayout" not in appearance_layouts.__all__
    assert not hasattr(appearance, "SimpleLayout")
    assert not hasattr(appearance_layouts, "SimpleLayout")

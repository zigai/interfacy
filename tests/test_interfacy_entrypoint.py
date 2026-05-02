import inspect

import pytest

import interfacy
from interfacy import Interfacy
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


def test_interfacy_exposes_public_parser_api() -> None:
    parser = Interfacy(sys_exit_enabled=False)

    for name in ("add_command", "add_group", "get_commands", "parse_args", "build_parser", "run"):
        assert callable(getattr(parser, name))


def test_interfacy_rejects_argparse_only_formatter_for_click_backend() -> None:
    with pytest.raises(ConfigurationError, match="formatter_class is only supported"):
        Interfacy(backend="click", formatter_class=object)


def test_interfacy_runs_with_selected_backend() -> None:
    def greet(name: str) -> str:
        return f"Hello, {name}!"

    parser = Interfacy(sys_exit_enabled=False)

    assert parser.run(greet, args=["Ada"]) == "Hello, Ada!"


def test_interfacy_rejects_unknown_backend() -> None:
    with pytest.raises(ConfigurationError, match="backend must be one of: argparse, click"):
        Interfacy(backend="unknown")


def test_backend_classes_are_not_top_level_exports() -> None:
    assert "Interfacy" in interfacy.__all__
    assert "Argparser" not in interfacy.__all__
    assert "ClickParser" not in interfacy.__all__

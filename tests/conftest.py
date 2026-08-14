import pytest

from interfacy import Interfacy
from interfacy.naming import DefaultFlagStrategy


@pytest.fixture
def parser(request: pytest.FixtureRequest) -> Interfacy:
    fixture_name = request.param
    return request.getfixturevalue(fixture_name)


@pytest.fixture
def argparse_req_pos() -> Interfacy:
    parser = Interfacy(
        backend="argparse",
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        full_error_traceback=True,
        help_layout=None,
        print_result=True,
    )
    parser.metadata["flag_style"] = "required_positional"
    return parser


@pytest.fixture
def argparse_kw_only() -> Interfacy:
    parser = Interfacy(
        backend="argparse",
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        full_error_traceback=True,
        help_layout=None,
        print_result=True,
    )
    parser.metadata["flag_style"] = "keyword_only"
    return parser


@pytest.fixture
def click_req_pos() -> Interfacy:
    pytest.importorskip("click")
    parser = Interfacy(
        backend="click",
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        full_error_traceback=True,
        help_layout=None,
        print_result=True,
    )
    parser.metadata["flag_style"] = "required_positional"
    return parser


@pytest.fixture
def click_kw_only() -> Interfacy:
    pytest.importorskip("click")
    parser = Interfacy(
        backend="click",
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        full_error_traceback=True,
        help_layout=None,
        print_result=True,
    )
    parser.metadata["flag_style"] = "keyword_only"
    return parser

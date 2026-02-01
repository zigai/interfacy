import pytest

from interfacy.naming import DefaultFlagStrategy

pytest.importorskip("click")

from interfacy import ClickParser


@pytest.fixture
def click_req_pos():
    return ClickParser(
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        sys_exit_enabled=False,
        full_error_traceback=True,
        help_layout=None,
        print_result=True,
    )


@pytest.fixture
def click_kw_only():
    return ClickParser(
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        sys_exit_enabled=False,
        full_error_traceback=True,
        help_layout=None,
        print_result=True,
    )

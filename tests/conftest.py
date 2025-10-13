import enum
from typing import Literal

import pytest

from interfacy.argparse_backend import Argparser
from interfacy.naming import DefaultFlagStrategy


def pow(base: int, exponent: int = 2) -> int:
    """
    Raise base to the power of exponent.

    Args:
        base (int): The base number.
        exponent (int, optional): The power to which the base is raised.

    Returns:
        int: Result of base raised to exponent.
    """
    return base**exponent


class Math:
    """
    A simple math class.

    Args:
        rounding (int, optional): The number of decimal places to round to.

    """

    def __init__(self, rounding: int = 6) -> None:
        self.rounding = rounding

    def _round(self, value: float | int) -> float | int:
        return round(value, self.rounding)

    def pow(self, base: int, exponent: int = 2) -> float:
        """
        Raise base to the power of exponent.

        Args:
            base (int): The base number.
            exponent (int, optional): The power to which the base is raised.

        Returns:
            float: Result of base raised to exponent.
        """
        return self._round(base**exponent)

    def add(self, a: int, b: int) -> float:
        """
        Add two numbers.

        Args:
            a (int): First number.
            b (int): Second number.

        Returns:
            float: Sum of a and b.
        """

        return self._round(a + b)

    def subtract(self, a: int, b: int) -> float:
        """
        Subtract two numbers.

        Args:
            a (int): First number.
            b (int): Second number.

        Returns:
            float: Difference of a and b.
        """
        return self._round(a - b)


class Color(enum.Enum):
    RED = 1
    GREEN = 2
    BLUE = 3


ColorLiteral = Literal["RED", "GREEN", "BLUE"]


def function_enum_arg(color: Color):
    print(f"Value: {color.value}, Name: {color.name}")
    return color


def function_literal_arg(color: ColorLiteral):
    print(f"Value: {color}")
    return color


def function_bool_required(value: bool):
    print(f"Value: {value}")
    return value


def function_bool_default_true(value: bool = True):
    print(f"Value: {value}")
    return value


def function_bool_default_false(value: bool = False):
    print(f"Value: {value}")
    return value


def function_bool_short_flag(x: bool = False):
    print(f"Value: {x}")
    return x


def function_list_int(values: list[int]):
    print(values)
    return values


def function_list_with_default(values: list[int] = [1, 2]):  # noqa: B006 - intentional for tests
    print(values)
    return values


def function_two_lists(strings: list[str], ints: list[int]) -> tuple[int, int]:
    print(strings, f"({len(strings)})")
    print(ints, f"({len(ints)})")
    return len(strings), len(ints)


@pytest.fixture
def parser(request):
    fixture_name = request.param
    return request.getfixturevalue(fixture_name)


@pytest.fixture
def argparse_req_pos():
    return Argparser(
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        sys_exit_enabled=False,
        full_error_traceback=True,
        help_layout=None,
        print_result=True,
    )


@pytest.fixture
def argparse_kw_only():
    return Argparser(
        flag_strategy=DefaultFlagStrategy(style="keyword_only"),
        sys_exit_enabled=False,
        full_error_traceback=True,
        help_layout=None,
        print_result=True,
    )

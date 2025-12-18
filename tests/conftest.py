import enum
from pathlib import Path
from typing import Dict, List, Literal, Optional, Union

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


def fn_enum_arg(color: Color):
    print(f"Value: {color.value}, Name: {color.name}")
    return color


def fn_literal_arg(color: ColorLiteral):
    print(f"Value: {color}")
    return color


def fn_enum_optional(color: Color | None = None):
    print(f"Value: {color}")
    return color


def fn_literal_optional(color: ColorLiteral | None = None):
    print(f"Value: {color}")
    return color


def fn_bool_required(value: bool):
    print(f"Value: {value}")
    return value


def fn_bool_default_true(value: bool = True):
    print(f"Value: {value}")
    return value


def fn_bool_default_false(value: bool = False):
    print(f"Value: {value}")
    return value


def fn_bool_short_flag(x: bool = False):
    print(f"Value: {x}")
    return x


def fn_list_int(values: list[int]):
    print(values)
    return values


def fn_list_with_default(values: list[int] = [1, 2]):  # noqa: B006 - intentional for tests
    print(values)
    return values


def fn_two_lists(strings: list[str], ints: list[int]) -> tuple[int, int]:
    print(strings, f"({len(strings)})")
    print(ints, f"({len(ints)})")
    return len(strings), len(ints)


def fn_list_str(items: list[str]):
    """Required list of strings."""
    return items


def fn_list_str_optional(items: list[str] | None = None):
    """Optional union list of strings (defaults to None)."""
    return items


def fn_list_int_optional(values: list[int] | None = None):
    """Optional union list of ints (defaults to None)."""
    return values


def fn_str_required(name: str) -> str:
    return name


def fn_str_optional(name: str = "default") -> str:
    return name


def fn_float_required(value: float) -> float:
    return value


def fn_path_required(path: Path) -> Path:
    return path


def fn_optional_str(value: str | None = None) -> str | None:
    return value


def fn_optional_int(value: int | None = None) -> int | None:
    return value


def fn_mixed_optional(
    required: str,
    optional_int: int | None = None,
    optional_str: str = "default",
) -> dict[str, object]:
    return {
        "required": required,
        "optional_int": optional_int,
        "optional_str": optional_str,
    }


def fn_positional_only(a: int, b: int, /) -> int:
    return a + b


def fn_keyword_only(*, a: int, b: int) -> int:
    return a + b


def fn_varargs(*args: int) -> int:
    return sum(args)


def fn_kwargs(**kwargs: str) -> dict[str, str]:
    return kwargs


def fn_all_zones(a: int, /, b: int, *, c: int) -> int:
    return a + b + c


def fn_legacy_list(x: List[int]) -> List[int]:
    return x


def fn_legacy_dict(x: Dict[str, int]) -> Dict[str, int]:
    return x


def fn_legacy_optional(x: Optional[int] = None) -> Optional[int]:
    return x


def fn_legacy_union(x: Union[int, str]) -> Union[int, str]:
    return x


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

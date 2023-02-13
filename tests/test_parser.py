import datetime
import decimal
import enum
import fractions
import json
import pathlib
from typing import Any, Callable

import pytest

from interfacy_cli.parser import PARSER


class MyType:
    ...


class MyEnum(enum.Enum):
    a = 1
    b = 2
    c = 3


STR_ABCD = "a, b,c,d"
LIST_ABCD = ["a", "b", "c", "d"]
STR_NUMS = "1,2,3,4,5"
LIST_NUMS = [1, 2, 3, 4, 5]


def test_basic_types():
    assert PARSER.parse("1.5", float) == 1.5
    assert PARSER.parse("5", int) == 5
    assert PARSER.parse("1/3", fractions.Fraction) == fractions.Fraction("1/3")
    assert PARSER.parse("./here.txt", pathlib.Path) == pathlib.Path("./here.txt")


def test_datetime():
    date = datetime.datetime(year=2022, day=19, month=7)
    assert PARSER.parse("2022.07.19", datetime.datetime) == date
    assert PARSER.parse("2022/07/19", datetime.datetime) == date
    assert PARSER.parse("19-7-2022", datetime.datetime) == date
    assert PARSER.parse("July 19th 2022", datetime.datetime) == date


def test_date():
    date = datetime.date(year=2022, day=19, month=7)
    assert PARSER.parse("2022.07.19", datetime.date) == date
    assert PARSER.parse("2022/07/19", datetime.date) == date
    assert PARSER.parse("19-7-2022", datetime.date) == date
    assert PARSER.parse("July 19th 2022", datetime.date) == date


def test_list_basic():
    assert PARSER.parse(STR_ABCD, list) == LIST_ABCD
    assert PARSER.parse(STR_ABCD, list) == LIST_ABCD
    assert PARSER.parse("./abcd_lines.txt", list) == LIST_ABCD
    assert PARSER.parse("./abcd_one_line.txt", list) == LIST_ABCD


def test_list_advanced():
    assert PARSER.parse("./12345_lines.txt", list[int]) == LIST_NUMS
    assert PARSER.parse(STR_NUMS, list[int]) == LIST_NUMS
    assert PARSER.parse("1/2,1/8,  1/3", list[fractions.Fraction]) == [
        fractions.Fraction("1/2"),
        fractions.Fraction("1/8"),
        fractions.Fraction("1/3"),
    ]


def test_dict():
    d = {"a": 1, "b": 2, "c": 3}
    assert PARSER.parse('{"a":1,"b":2,"c":3}', dict) == d
    assert PARSER.parse("./abc.json", dict) == d


def test_set():
    assert PARSER.parse(STR_ABCD, set) == set(LIST_ABCD)
    assert PARSER.parse(STR_NUMS, set[int]) == set(LIST_NUMS)
    assert PARSER.parse(STR_ABCD, set[str]) == set(LIST_ABCD)


def test_enum():
    assert PARSER.parse("a", MyEnum) == MyEnum.a
    with pytest.raises(KeyError):
        PARSER.parse("d", MyEnum)


def test_range():
    assert PARSER.parse("1:5", range) == range(1, 5)
    assert PARSER.parse("  1:5", range) == range(1, 5)
    assert PARSER.parse("1:5:-1", range) == range(1, 5, -1)
    assert PARSER.parse("1    :  5   :   -1", range) == range(1, 5, -1)


def test_slice():
    assert PARSER.parse("1:5", slice) == slice(1, 5)
    assert PARSER.parse("  1:5", slice) == slice(1, 5)
    assert PARSER.parse("1:5:9", slice) == slice(1, 5, 9)
    assert PARSER.parse("1.5:5.5", slice) == slice(1.5, 5.5)


def test_alias_types():
    d = {"a": 1, "b": 2, "c": 3}
    assert PARSER.parse("./abc_list.json", list[dict]) == [d, d, d]
    assert PARSER.parse("1,2,3,4,5", list[int]) == [1, 2, 3, 4, 5]
    assert PARSER.parse("1,2,3,4,5", set[int]) == set([1, 2, 3, 4, 5])
    """
    assert PARSER.parse("./nested_list.txt", list[list[int]]) == [
        [1, 2, 3, 4, 5],
        [1, 2, 3, 4, 5],
        [1, 2, 3, 4, 5],
        [1, 2, 3, 4, 5],
        [1, 2, 3, 4, 5],
    ]
    """


"""
def test_supported():
    assert PARSER.is_supported(int) == True
    assert PARSER.is_supported(float) == True
    assert PARSER.is_supported(list) == True
    assert PARSER.is_supported(list[int]) == True
    assert PARSER.is_supported(list[float]) == True
    assert PARSER.is_supported(MyType) == False
    assert PARSER.is_supported(list[MyType]) == False
    assert PARSER.is_supported(list[list[int]]) == True
"""

import pytest
from interfacy_cli.cli_parsers import *

str_abcd = "a,b,c,d"
str_nums = "1,2,3,4,5"
list_str = ["a", "b", "c", "d"]
list_int = [1, 2, 3, 4, 5]


def test_list_from_str():
    assert CLI_PARSER[list](str_abcd) == list_str


def test_list_from_file_lines():
    assert CLI_PARSER[list]("./list_lines.txt") == list_str


def test_list_from_file_one_line():
    assert CLI_PARSER[list]("./list_str_one_line.txt") == list_str


def test_set_from_str():
    assert CLI_PARSER[set](str_abcd) == set(list_str)


def test_path():
    path = "/mnt/d/files/file.txt"
    assert CLI_PARSER[pathlib.Path](path) == pathlib.Path(path)


def test_datetime1():
    d = datetime.datetime.fromtimestamp(1658234928)
    assert CLI_PARSER[datetime.datetime]("2022.07.19 14:48:48") == d


def test_datetime2():
    d = datetime.datetime(year=2022, month=7, day=19)
    assert CLI_PARSER[datetime.datetime]("2022.07.19") == d


def test_datetime3():
    d = datetime.datetime(year=2022, month=7, day=19)
    assert CLI_PARSER[datetime.datetime]("2022/07/19") == d


def test_datetime4():
    d = datetime.datetime(year=2022, month=7, day=19)
    assert CLI_PARSER[datetime.datetime]("19-7-2022") == d


def test_datetime5():
    d = datetime.datetime(year=2022, month=7, day=19)
    assert CLI_PARSER[datetime.datetime]("July 19th 2022") == d


def test_list_int():
    assert CLI_PARSER[list[int]](str_nums) == list_int

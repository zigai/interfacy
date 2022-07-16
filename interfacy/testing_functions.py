from datetime import date
from pprint import pp, pprint
from typing import List, Union

import pretty_errors


class test_cls1:
    """class dostring"""

    def __init__(self, a: str, b: int) -> None:
        self.a = a
        self.b = b
        print("init")

    def test(self):
        print("method test called")
        print(f"{self.a=}")
        print(f"{self.b=}")


def test_func1(a: str, b: int, c=1, d: bool = False):
    pp(vars())


def test_func2(
    a: int | float,
    aa: date,
    b: list[str],
    c: float | int | list[str] = 1,
    d: dict = {},
):
    """
    func dostring
    """
    pp(vars())


def test_func3(a: List[str], b: Union[int, float]):
    pp(vars())


def main():
    from interfacy import Interfacy
    from interfacy.cli import CLI

    CLI(test_func1).build()


if __name__ == '__main__':
    main()

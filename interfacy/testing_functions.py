from datetime import date
from pprint import pp, pprint
from typing import List, Union

import pretty_errors

from interfacy import CLI
from interfacy.interfacy_class import InterfacyClass


class test_cls1:
    """class dostring"""

    def __init__(self, a: str, b: int) -> None:
        """init docstring"""
        self.a = a
        self.b = b
        print("init")

    def method1(self):
        """test docstring"""
        print("method test called")
        print(f"{self.a=}")
        print(f"{self.b=}")

    def static_method1(self):
        """test docstring"""
        print("method test called")
        print(f"{self.a=}")
        print(f"{self.b=}")


class test_cls2:
    """class dostring"""

    @staticmethod
    def static_method1():
        """static_method1 docstring"""
        pass

    @staticmethod
    def static_method2():
        """static_method1 docstring"""
        pass


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
    """
    a = InterfacyClass(test_cls1)
    print(a)
    a = InterfacyClass(test_cls2)
    print(a)
    """
    CLI(test_func2).run()


if __name__ == '__main__':
    main()

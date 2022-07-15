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


def test_func1(a: str, b: int, c: float):
    print(f"{a=}")
    print(f"{b=}")
    print(f"{c=}")


def test_func2(a: int | float, b: list[str], c: float | int | list[str] = 1, d: dict = {}):
    """
    func dostring
    """
    print(f"{a=}")
    print(f"{b=}")
    print(f"{c=}")


from typing import List, Union


def test_func3(a: List[str], b: Union[int, float]):
    print(f"{a=}")
    print(f"{b=}")

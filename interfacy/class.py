import inspect
from pprint import pp, pprint

from interfacy.function import InterfacyFunction
from interfacy.parameter import InterfacyParameter
from testing_functions import test_cls1, test_cls2


class InterfacyClass:

    def __init__(self, cls) -> None:
        self.cls = cls
        self.name: str = self.cls.__name__
        self.docstr = inspect.getdoc(self.cls)
        if self.docstr is None:
            self.docstr = ""
        members = inspect.getmembers(self.cls, inspect.isfunction)
        self.has_init = members[0][0] == "__init__"
        self.methods = [InterfacyFunction(i[1]) for i in members]

    @property
    def has_docstr(self):
        return len(self.docstr) != 0

    def __repr__(self) -> str:
        return f"InterfacyClass(name={self.name}, methods={len(self.methods)}, has_init={self.has_init}, has_docstr={self.has_docstr})"


def main():
    a = InterfacyClass(test_cls1)
    print(a)

    a = InterfacyClass(test_cls2)
    print(a)


if __name__ == '__main__':
    main()

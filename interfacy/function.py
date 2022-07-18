import inspect

from interfacy.parameter import InterfacyParameter


class InterfacyFunction:

    def __init__(self, func) -> None:
        self.func = func
        self.name: str = self.func.__name__
        self.docstr = inspect.getdoc(self.func)
        if self.docstr is None:
            self.docstr = ""
        self.parameters = self._get_parameters()

    @property
    def has_docstr(self):
        return len(self.docstr) != 0

    def __repr__(self) -> str:
        return f"InterfacyFunction(name={self.name}, parameters={len(self.parameters)}, has_docstr={self.has_docstr})"

    def _get_parameters(self):
        func_args = inspect.signature(self.func)
        return [InterfacyParameter(i) for i in func_args.parameters.values()]


def main():
    from interfacy.testing_functions import test_func1
    InterfacyFunction(test_func1)


if __name__ == '__main__':
    main()

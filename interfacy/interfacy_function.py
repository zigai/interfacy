import inspect

from interfacy.interfacy_parameter import InterfacyParameter


class InterfacyFunction:

    def __init__(self, func) -> None:
        self.func = func
        self.name: str = self.func.__name__
        self.docstr = inspect.getdoc(self.func)
        if self.docstr is None:
            self.docstr = ""
        func_args = inspect.signature(self.func)
        self.parameters = [InterfacyParameter(i) for i in func_args.parameters.values()]

    @property
    def has_docstr(self) -> bool:
        return len(self.docstr) != 0

    def __repr__(self) -> str:
        return f"InterfacyFunction(name={self.name}, parameters={len(self.parameters)}, has_docstr={self.has_docstr})"

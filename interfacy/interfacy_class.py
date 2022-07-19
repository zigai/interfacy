import inspect

from interfacy.interfacy_function import InterfacyFunction


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
    def has_docstr(self) -> bool:
        return len(self.docstr) != 0

    def __repr__(self) -> str:
        return f"InterfacyClass(name={self.name}, methods={len(self.methods)}, has_init={self.has_init}, has_docstr={self.has_docstr})"

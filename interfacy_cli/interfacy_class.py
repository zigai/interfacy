import inspect

from interfacy_cli.interfacy_function import InterfacyFunction


class InterfacyClass:
    def __init__(self, cls) -> None:
        self.cls = cls
        self.name: str = self.cls.__name__
        self.docstring = inspect.getdoc(self.cls)
        self.has_docstring = self.__has_docstring()
        members = inspect.getmembers(self.cls, inspect.isfunction)
        self.has_init = members[0][0] == "__init__"
        self.methods = [InterfacyFunction(i[1], self.name) for i in members]

    def __has_docstring(self) -> bool:
        if self.docstring is not None:
            if len(self.docstring):
                return True
        return False

    @property
    def dict(self):
        return {"name": self.name, "methods": [i.dict for i in self.methods]}

    def __repr__(self) -> str:
        return f"Class(name={self.name}, methods={len(self.methods)}, has_init={self.has_init}, docstring={self.docstring})"

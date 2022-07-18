import inspect

from interfacy.parameter import InterfacyParameter


class InterfacyFunction:

    def __init__(self, func) -> None:
        self.func = func
        self.docstr = inspect.getdoc(self.func)
        if self.docstr is None:
            self.docstr = ""
        self.parameters = self._get_parameters()

    def __repr__(self) -> str:
        return f"InterfacyFunction({id(self)})"

    def _get_parameters(self):
        func_args = inspect.signature(self.func)
        return [InterfacyParameter(i) for i in func_args.parameters.values()]

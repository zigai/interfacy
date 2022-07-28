import inspect

import docstring_parser

from interfacy.interfacy_parameter import InterfacyParameter


class InterfacyFunction:

    def __init__(self, func, owner: str | None = None) -> None:
        self.func = func
        self.name: str = self.func.__name__
        self.owner = owner
        self.docstring = inspect.getdoc(self.func)
        self.has_docstring = self.__has_docstring()
        if self.has_docstring:
            self.__parsed_docstr = docstring_parser.parse(self.docstring)
        else:
            self.__parsed_docstr = None
        self.parameters = self.__get_parameters()
        self.description = self.__get_description()

    def __get_parameters(self):
        args = inspect.signature(self.func)
        parameters = [
            InterfacyParameter.from_inspect_param(i, owner=self.name)
            for i in args.parameters.values()
        ]

        # Try finding descriptions for parameters
        if self.has_docstring:
            params_map = {p.arg_name: p for p in self.__parsed_docstr.params}
            for param in parameters:
                if docstr_param := params_map.get(param.name, False):
                    if docstr_param.description:
                        param.description = docstr_param.description
        return parameters

    def __has_docstring(self) -> bool:
        if self.docstring is not None:
            if len(self.docstring):
                return True
        return False

    def __get_description(self):
        if self.__parsed_docstr is None:
            return ""
        if self.__parsed_docstr.short_description:
            return self.__parsed_docstr.short_description
        if self.__parsed_docstr.long_description:
            return self.__parsed_docstr.long_description
        return ""

    @property
    def dict(self):
        return {
            "name": self.name,
            "parameters": [i.dict for i in self.parameters],
            "docstring": self.docstring,
        }

    def __repr__(self) -> str:
        return f"Function(name={self.name}, parameters={len(self.parameters)}, docstring={self.docstring}, owner={self.owner})"

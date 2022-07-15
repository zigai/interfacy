import inspect

EMPTY = inspect._empty


class InterfacyParameter:

    def __init__(self, param: inspect.Parameter) -> None:
        self.type = param.annotation
        self.name = param.name
        self.default = param.default

    @property
    def dict(self):
        return {
            "name": self.name,
            "type": self.type,
            "default": self.default,
        }

    def __repr__(self):
        return f"InterfacyParameter(type={self.type}, name={self.name}, default={self.default})"

    @property
    def is_typed(self) -> bool:
        return self.type != EMPTY

    @property
    def is_required(self) -> bool:
        return self.default == EMPTY

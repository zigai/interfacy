from objinspect.util import type_to_str


class InterfacyException(Exception):
    pass


class UnsupportedParamError(InterfacyException):
    def __init__(self, t):
        self.msg = f"Parameter of type '{type_to_str(t)}' is not supported"
        super().__init__(self.msg)


class ReservedFlagError(InterfacyException):
    def __init__(self, flag: str):
        self.msg = f"'{flag}' is a reserved flag"
        super().__init__(self.msg)

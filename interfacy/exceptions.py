from interfacy.util import type_as_str


class UnsupportedParamError(Exception):

    def __init__(self, t):
        self.msg = f"Parameter of type '{type_as_str(t)}' is not supported"
        super().__init__(self.msg)


class ReservedFlagError(Exception):

    def __init__(self, flag):
        self.msg = f"'{flag}' is a reserved flag"
        super().__init__(self.msg)

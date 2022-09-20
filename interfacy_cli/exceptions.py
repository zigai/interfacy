from interfacy_core.exceptions import InterfacyException


class ReservedFlagError(InterfacyException):
    def __init__(self, flag: str):
        self.msg = f"'{flag}' is a reserved flag"
        super().__init__(self.msg)

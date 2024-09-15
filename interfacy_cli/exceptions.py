class InterfacyException(Exception):
    pass


class UnsupportedParamError(InterfacyException):
    def __init__(self, t):
        self.msg = f"Parameter of type '{t}' is not supported"
        super().__init__(self.msg)


class ReservedFlagError(InterfacyException):
    def __init__(self, flag: str):
        self.msg = f"'{flag}' is a reserved flag"
        super().__init__(self.msg)


class InvalidCommandError(InterfacyException):
    def __init__(self, command):
        super().__init__(f"'{command}' is not a valid command")


class DuplicateCommandError(InterfacyException):
    def __init__(self, command: str):
        self.msg = f"Duplicate command '{command}'"
        super().__init__(self.msg)

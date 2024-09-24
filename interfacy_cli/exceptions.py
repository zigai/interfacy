class InterfacyException(Exception):
    pass


class UnsupportedParamError(InterfacyException):
    def __init__(self, t):
        self.param_t = t
        super().__init__(f"Parameter of type '{t}' is not supported")


class ReservedFlagError(InterfacyException):
    def __init__(self, flag: str):
        self.flag = flag
        super().__init__(f"'{flag}' is a reserved flag")


class InvalidCommandError(InterfacyException):
    def __init__(self, command):
        self.command = command
        super().__init__(f"'{command}' is not a valid command")


class DuplicateCommandError(InterfacyException):
    def __init__(self, command):
        self.command = command
        super().__init__(f"Duplicate command '{command}'")

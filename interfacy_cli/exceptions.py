class InterfacyError(Exception):
    pass


class UnsupportedParameterTypeError(InterfacyError):
    def __init__(self, t):
        self.param_t = t
        super().__init__(f"Parameter of type '{t}' is not supported")


class ReservedFlagError(InterfacyError):
    def __init__(self, flag: str):
        self.flag = flag
        super().__init__(f"Flag name '{flag}' is already reserved for a different flag")


class InvalidCommandError(InterfacyError):
    def __init__(self, command):
        self.command = command
        super().__init__(f"'{command}' is not a valid command")


class DuplicateCommandError(InterfacyError):
    def __init__(self, command):
        self.command = command
        super().__init__(f"Duplicate command '{command}'")


class InvalidConfigurationError(InterfacyError):
    def __init__(self, message: str) -> None:
        super().__init__(message)

from objinspect.constants import *

ITEM_SEP = ","
RESERVED_FLAGS = ["h", "help"]
SIMPLE_TYPES = [str, bool]
COMMAND_KEY = "command"
ITER_SEP = ","
RANGE_SEP = ":"


class ExitCode:
    SUCCESS = 0
    RUNTIME_ERR = 1
    INVALID_ARGS = 2
    PARSING_ERR = 3

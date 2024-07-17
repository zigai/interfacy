ITEM_SEP = ","
ARGPARSE_RESERVED_FLAGS = ["h", "help"]

SIMPLE_TYPES = [str, bool]
COMMAND_KEY = "command"
ITER_SEP = ","
RANGE_SEP = ":"


class ExitCode:
    SUCCESS = 0
    INVALID_ARGS_ERR = 1
    RUNTIME_ERR = 2
    PARSING_ERR = 3

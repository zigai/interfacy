ITEM_SEP = ","
ARGPARSE_RESERVED_FLAGS = ["h", "help"]
CLICK_RESERVED_FLAGS = ["help"]
SIMPLE_TYPES = [str, bool]
COMMAND_KEY = "command"
ITER_SEP = ","
RANGE_SEP = ":"


class ExitCode:
    SUCCESS = 0
    RUNTIME_ERR = 1
    INVALID_ARGS = 2
    PARSING_ERR = 3

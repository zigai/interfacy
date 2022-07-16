import os
from typing import get_args, get_origin


def type_as_str(t):
    type_str = repr(t)
    if "<class '" in type_str:
        type_str = type_str.split("'")[1]
    return type_str


def is_file(s):
    return os.path.isfile(s)

import os
from typing import Any, Callable, Iterable, Mapping


def is_file(path: str) -> bool:
    return os.path.isfile(path)


def cast_to(t):
    """
    Returns a functions that casts a string to type 't'
    """

    def inner(arg: str) -> t:
        if isinstance(arg, t):
            return arg
        return t(arg)

    return inner


def cast(value: Any, t: Any):
    if isinstance(value, t):
        return value
    return t(value)


def cast_iter_to(iterable: Iterable, t: Any):
    def inner(arg) -> iterable[t]:
        l = [t(i) for i in arg]
        return iterable(l)

    return inner


def cast_dict_to(k: Any, v: Any):
    def inner(arg: dict) -> dict[k, v]:
        return {k(key): v(val) for key, val in arg.items()}

    return inner


def parse_and_cast(parser: Callable, caster: Any):
    def inner(val):
        if isinstance(val, caster):
            return val
        return caster(parser(val))

    return inner

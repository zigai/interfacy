import os


def type_as_str(t):
    type_str = repr(t)
    if "<class '" in type_str:
        type_str = type_str.split("'")[1]
    return type_str


def cast_to(t):
    """
    Returns a functions that casts a string to type 't'
    """

    def inner(arg: str) -> t:
        if isinstance(arg, t):
            return arg
        return t(arg)

    return inner


def cast_iter_to(iterable, t):
    def inner(arg) -> iterable[t]:
        l = [t(i) for i in arg]
        return iterable(l)

    return inner


def cast_dict_to(k, v):
    def inner(arg: dict) -> dict[k, v]:
        return {k(key): v(val) for key, val in arg.items()}

    return inner


def parse_then_cast(parser, caster):
    def inner(val: str):
        return caster(parser(val))

    return inner


def extract_enum_options(e):
    return tuple(e.__members__.keys())

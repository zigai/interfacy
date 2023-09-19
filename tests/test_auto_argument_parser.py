import objinspect
from data import Math, pow

from interfacy_cli.auto_argparse_parser import AutoArgparseParser


def test_from_function():
    func = objinspect.Function(pow)
    auto_parser = AutoArgparseParser(description=func.description)
    parser = auto_parser.parser_from_func(func)
    assert parser.description == func.description

    args = parser.parse_args(["2", "-e", "2"])
    assert args.base == "2"
    assert args.exponent == "2"

    args = parser.parse_args(["2"])
    assert args.base == "2"
    assert args.exponent == 2


def test_from_method():
    math = Math()
    method = objinspect.objinspect(math.pow)
    assert isinstance(method, objinspect.Method)
    auto_parser = AutoArgparseParser(description=method.description)
    parser = auto_parser.parser_from_method(method, taken_flags=["-h", "--help"])
    assert parser.description == method.description

    args = parser.parse_args(["2", "-e", "2"])
    assert args.base == "2"
    assert args.exponent == "2"

    args = parser.parse_args(["2"])
    assert args.base == "2"
    assert args.exponent == 2

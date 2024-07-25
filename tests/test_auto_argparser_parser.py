import objinspect
from data import Math, pow

from interfacy_cli.argparse_parser import ArgparseParser


def test_from_function():
    func = objinspect.Function(pow)
    auto_parser = ArgparseParser(description=func.description)
    parser = auto_parser._parser_from_func(func)
    assert parser.description == func.description

    args = parser.parse_args(["2", "-e", "2"])
    assert args.base == 2
    assert args.exponent == 2

    args = parser.parse_args(["2"])
    assert args.base == 2
    assert args.exponent == 2


def test_from_method():
    math = Math()
    method = objinspect.inspect(math.pow)
    assert isinstance(method, objinspect.Method)
    auto_parser = ArgparseParser(description=method.description)
    parser = auto_parser.parser_from_method(method, taken_flags=["-h", "--help"])
    assert parser.description == method.description

    args = parser.parse_args(["2", "-e", "2"])
    assert args.base == 2
    assert args.exponent == 2

    args = parser.parse_args(["2"])
    assert args.base == 2
    assert args.exponent == 2


def test_from_instance():
    cls = objinspect.Class(Math())

    auto_parser = ArgparseParser(description=cls.description)
    parser = auto_parser._parser_from_class(cls)
    assert parser.description == cls.description

    args = parser.parse_args(["pow", "2", "-e", "2"])
    assert args.command == "pow"
    namespace = args.pow
    assert namespace.base == 2
    assert namespace.exponent == 2

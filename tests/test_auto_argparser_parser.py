import objinspect
from data import Math, pow

from interfacy_cli.argparse_parser import Argparser


def test_from_function():
    func = objinspect.Function(pow)
    parser = Argparser(description=func.description)
    parser = parser.parser_from_function(func)
    assert parser.description == func.description

    args = parser.parse_args(["pow", "2", "-e", "2"])
    assert args.base == 2
    assert args.exponent == 2

    args = parser.parse_args(["2"])
    assert args.base == 2
    assert args.exponent == 2


def test_from_method():
    math = Math()
    parser = Argparser()
    parser.add_command(math.pow)

    args = parser.parse_args(["pow", "2", "-e", "2"])

    assert args.base == 2
    assert args.exponent == 2

    args = parser.parse_args(["2"])
    assert args.base == 2
    assert args.exponent == 2


def test_from_instance():
    cls = objinspect.Class(Math())

    parser = Argparser(description=cls.description)
    parser = parser.parser_from_class(cls)
    assert parser.description == cls.description

    args = parser.parse_args(["pow", "2", "-e", "2"])
    assert args.command == "pow"
    namespace = args.pow
    assert namespace.base == 2
    assert namespace.exponent == 2

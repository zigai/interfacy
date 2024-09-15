import objinspect
from data import Math, pow

from interfacy_cli.click_parser import ClickParser


def test_from_function():
    func = objinspect.Function(pow)
    parser = ClickParser()
    parser.add_command(pow)

    args = parser.run(["pow", "2", "-e", "2"])
    assert args.base == 2
    assert args.exponent == 2

    args = parser.run(["2"])
    assert args.base == 2
    assert args.exponent == 2

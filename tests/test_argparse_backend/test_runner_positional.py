from interfacy_cli.argparse_backend import Argparser
from interfacy_cli.core import BasicFlagStrategy

from ..inputs import *


def new_parser():
    return Argparser(flag_strategy=BasicFlagStrategy(style="required_positional"))


def test_from_function():
    result = new_parser().run(pow, args=["2", "-e", "2"])
    assert result == 4

    result = new_parser().run(pow, args=["2"])
    assert result == 4

    parser = new_parser()
    parser.add_command(pow)
    result = parser.run(args=["2"])
    assert result == 4


def test_bool():
    assert new_parser().run(func_with_bool_arg, args=["--value"]) == True
    assert new_parser().run(func_with_bool_arg, args=["--no-value"]) == False


def test_bool_true_by_default():
    assert new_parser().run(func_with_bool_default_true, args=["--value"]) == True
    assert new_parser().run(func_with_bool_default_true, args=["--no-value"]) == False
    assert new_parser().run(func_with_bool_default_true, args=[]) == True


def test_bool_false_by_default():
    assert new_parser().run(func_with_bool_default_false, args=["--value"]) == True
    assert new_parser().run(func_with_bool_default_false, args=["--no-value"]) == False
    assert new_parser().run(func_with_bool_default_false, args=[]) == False


"""


def test_from_class():
    result = new_parser().run(Math, args=["pow", "2", "-e", "2"])
    assert result == 4
    result = new_parser().run(Math, args=["add", "1", "1"])
    assert result == 2


def test_from_instance():
    instance = Math(rounding=1)
    result = new_parser().run(instance, args=["pow", "2", "-e", "2"])
    assert result == 4
    result = new_parser().run(instance, args=["add", "1", "1"])
    assert result == 2


def test_from_instance():
    parser = new_parser()
    math = Math(rounding=2)
    parser.add_command(math)

    namespace = parser.parse_args(["pow", "2", "-e", "2"])
    assert namespace["command"] == "pow"

    namespace = namespace["pow"]
    assert namespace["base"] == 2
    assert namespace["exponent"] == 2


def test_from_method():
    parser = new_parser()
    math = Math(rounding=2)
    parser.add_command(math.pow)

    namespace = parser.parse_args(["2", "-e", "2"])
    assert namespace["base"] == 2
    assert namespace["exponent"] == 2

    namespace = parser.parse_args(["2"])
    assert namespace["base"] == 2
    assert namespace["exponent"] == 2


"""

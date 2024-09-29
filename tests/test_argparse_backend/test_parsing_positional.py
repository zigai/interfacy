from interfacy_cli.argparse_backend import Argparser
from interfacy_cli.core import BasicFlagStrategy

from ..inputs import *


def new_parser():
    return Argparser(flag_strategy=BasicFlagStrategy(style="required_positional"))


def test_from_function():
    parser = new_parser()
    parser.add_command(pow)

    namespace = parser.parse_args(["2", "-e", "2"])
    assert namespace["base"] == 2
    assert namespace["exponent"] == 2

    namespace = parser.parse_args(["2"])
    assert namespace["base"] == 2
    assert namespace["exponent"] == 2


def test_from_class():
    parser = new_parser()
    parser.add_command(Math)

    namespace = parser.parse_args(["pow", "2", "-e", "2"])
    assert namespace["command"] == "pow"
    assert namespace["rounding"] == 6

    namespace = namespace["pow"]
    assert namespace["base"] == 2
    assert namespace["exponent"] == 2


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


def test_from_multiple():
    parser = new_parser()
    parser.add_command(pow)
    parser.add_command(Math)

    namespace = parser.parse_args(["pow", "2", "-e", "2"])
    assert namespace["command"] == "pow"
    assert namespace["pow"]["base"] == 2
    assert namespace["pow"]["exponent"] == 2

    namespace = parser.parse_args(["math", "pow", "2", "-e", "2"])
    assert namespace["command"] == "math"
    assert namespace["math"]["command"] == "pow"
    assert namespace["math"]["rounding"] == 6
    assert namespace["math"]["pow"]["base"] == 2
    assert namespace["math"]["pow"]["exponent"] == 2


def test_list_nargs():
    parser = new_parser()
    parser.add_command(func_nargs)
    namespace = parser.parse_args(["1", "2", "3"])
    assert namespace["values"] == [1, 2, 3]


def test_list_two_positional():
    parser = new_parser()
    parser.add_command(func_nargs_two_positional)
    namespace = parser.parse_args(["a", "b", "--ints", "1", "2"])
    assert namespace["strs"] == ["a", "b"]
    assert namespace["ints"] == [1, 2]


def test_bool():
    parser = new_parser()
    parser.add_command(func_with_bool_arg)

    namespace = parser.parse_args(["--value"])
    assert namespace["value"] == True

    namespace = parser.parse_args(["--no-value"])
    assert namespace["value"] == False


def test_bool_true_by_default():
    parser = new_parser()
    parser.add_command(func_with_bool_default_true)

    namespace = parser.parse_args([])
    assert namespace["value"] == True

    namespace = parser.parse_args(["--value"])
    assert namespace["value"] == True

    namespace = parser.parse_args(["--no-value"])
    assert namespace["value"] == False


def test_bool_false_by_default():
    parser = new_parser()
    parser.add_command(func_with_bool_default_false)

    namespace = parser.parse_args([])
    assert namespace["value"] == False

    namespace = parser.parse_args(["--value"])
    assert namespace["value"] == True

    namespace = parser.parse_args(["--no-value"])
    assert namespace["value"] == False

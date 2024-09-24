from interfacy_cli.argparse_backend import Argparser

from ..inputs import *


def test_from_function():
    parser = Argparser()
    parser.add_command(pow)

    namespace = parser.parse_args(["2", "-e", "2"])
    assert namespace["base"] == 2
    assert namespace["exponent"] == 2

    namespace = parser.parse_args(["2"])
    assert namespace["base"] == 2
    assert namespace["exponent"] == 2


def test_from_class():
    parser = Argparser()
    parser.add_command(Math)

    namespace = parser.parse_args(["pow", "2", "-e", "2"])
    assert namespace["command"] == "pow"
    assert namespace["rounding"] == 6

    namespace = namespace["pow"]
    assert namespace["base"] == 2
    assert namespace["exponent"] == 2


def test_from_instance():
    parser = Argparser()
    math = Math(rounding=2)
    parser.add_command(math)

    namespace = parser.parse_args(["pow", "2", "-e", "2"])
    assert namespace["command"] == "pow"

    namespace = namespace["pow"]
    assert namespace["base"] == 2
    assert namespace["exponent"] == 2


def test_from_method():
    parser = Argparser()
    math = Math(rounding=2)
    parser.add_command(math.pow)

    namespace = parser.parse_args(["2", "-e", "2"])
    assert namespace["base"] == 2
    assert namespace["exponent"] == 2

    namespace = parser.parse_args(["2"])
    assert namespace["base"] == 2
    assert namespace["exponent"] == 2


def test_bool():
    parser = Argparser()
    parser.add_command(func_with_bool_arg)

    namespace = parser.parse_args(["--value"])
    assert namespace["value"] == True

    namespace = parser.parse_args(["--no-value"])
    assert namespace["value"] == False


def test_bool_true_by_default():
    parser = Argparser()
    parser.add_command(func_with_bool_default_true)

    namespace = parser.parse_args([])
    assert namespace["value"] == True

    namespace = parser.parse_args(["--value"])
    assert namespace["value"] == True

    namespace = parser.parse_args(["--no-value"])
    assert namespace["value"] == False


def test_bool_false_by_default():
    parser = Argparser()
    parser.add_command(func_with_bool_default_false)

    namespace = parser.parse_args([])
    assert namespace["value"] == False

    namespace = parser.parse_args(["--value"])
    assert namespace["value"] == True

    namespace = parser.parse_args(["--no-value"])
    assert namespace["value"] == False

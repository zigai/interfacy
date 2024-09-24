from interfacy_cli.argparse_backend import Argparser

from ..inputs import *


def test_from_function():
    result = Argparser().run(pow, args=["2", "-e", "2"])
    assert result == 4

    result = Argparser().run(pow, args=["2"])
    assert result == 4

    parser = Argparser()
    parser.add_command(pow)
    result = parser.run(args=["2"])
    assert result == 4


"""

def test_from_class():
    result = Argparser().run(Math, args=["pow", "2", "-e", "2"])
    assert result == 4
    result = Argparser().run(Math, args=["add", "1", "1"])
    assert result == 2


def test_from_instance():
    result = Argparser().run(Math(rounding=1), args=["pow", "2", "-e", "2"])
    assert result == 4
    result = Argparser().run(Math(rounding=1), args=["add", "1", "1"])
    assert result == 2

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
"""

from interfacy_cli import Argparser
from interfacy_cli.core import BasicFlagGenerator

from ..inputs import *


class TestParsingRequiredPositional:
    def new_parser(self):
        return Argparser(
            flag_strategy=BasicFlagGenerator(style="required_positional"),
            disable_sys_exit=True,
            full_error_traceback=True,
        )

    def test_from_function(self):
        parser = self.new_parser()
        parser.add_command(pow)
        namespace = parser.parse_args(["2", "-e", "2"])
        assert namespace["base"] == 2
        assert namespace["exponent"] == 2
        namespace = parser.parse_args(["2"])
        assert namespace["base"] == 2
        assert namespace["exponent"] == 2

    def test_from_class(self):
        parser = self.new_parser()
        parser.add_command(Math)
        namespace = parser.parse_args(["pow", "2", "-e", "2"])
        assert namespace["command"] == "pow"
        assert namespace["rounding"] == 6
        namespace = namespace["pow"]
        assert namespace["base"] == 2
        assert namespace["exponent"] == 2

    def test_from_instance(self):
        parser = self.new_parser()
        math = Math(rounding=2)
        parser.add_command(math)
        namespace = parser.parse_args(["pow", "2", "-e", "2"])
        assert namespace["command"] == "pow"
        namespace = namespace["pow"]
        assert namespace["base"] == 2
        assert namespace["exponent"] == 2

    def test_from_method(self):
        parser = self.new_parser()
        math = Math(rounding=2)
        parser.add_command(math.pow)
        namespace = parser.parse_args(["2", "-e", "2"])
        assert namespace["base"] == 2
        assert namespace["exponent"] == 2
        namespace = parser.parse_args(["2"])
        assert namespace["base"] == 2
        assert namespace["exponent"] == 2

    def test_from_multiple(self):
        parser = self.new_parser()
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

    def test_list_nargs(self):
        parser = self.new_parser()
        parser.add_command(func_nargs)
        namespace = parser.parse_args(["1", "2", "3"])
        assert namespace["values"] == [1, 2, 3]

    def test_list_two_positional(self):
        parser = self.new_parser()
        parser.add_command(func_nargs_two_positional)
        namespace = parser.parse_args(["a", "b", "--ints", "1", "2"])
        assert namespace["strs"] == ["a", "b"]
        assert namespace["ints"] == [1, 2]

    def test_bool(self):
        parser = self.new_parser()
        parser.add_command(func_with_bool_arg)
        namespace = parser.parse_args(["--value"])
        assert namespace["value"] == True
        namespace = parser.parse_args(["--no-value"])
        assert namespace["value"] == False

    def test_bool_true_by_default(self):
        parser = self.new_parser()
        parser.add_command(func_with_bool_default_true)
        namespace = parser.parse_args([])
        assert namespace["value"] == True
        namespace = parser.parse_args(["--value"])
        assert namespace["value"] == True
        namespace = parser.parse_args(["--no-value"])
        assert namespace["value"] == False

    def test_bool_false_by_default(self):
        parser = self.new_parser()
        parser.add_command(func_with_bool_default_false)
        namespace = parser.parse_args([])
        assert namespace["value"] == False
        namespace = parser.parse_args(["--value"])
        assert namespace["value"] == True
        namespace = parser.parse_args(["--no-value"])
        assert namespace["value"] == False


class TestParsingKeywordOnly:
    def new_parser(self):
        return Argparser(
            flag_strategy=BasicFlagGenerator(style="keyword_only"),
            disable_sys_exit=True,
            full_error_traceback=True,
        )

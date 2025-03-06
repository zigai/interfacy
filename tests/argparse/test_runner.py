import pytest

from interfacy import Argparser
from interfacy.core import BasicFlagGenerator

from ..inputs import *


class TestRunnerRequiredPositional:
    def new_parser(self):
        return Argparser(
            flag_strategy=BasicFlagGenerator(style="required_positional"),
            disable_sys_exit=True,
            full_error_traceback=True,
        )

    def test_from_function(self):
        result = self.new_parser().run(pow, args=["2", "-e", "2"])
        assert result == 4

        result = self.new_parser().run(pow, args=["2"])
        assert result == 4

        parser = self.new_parser()
        parser.add_command(pow)
        result = parser.run(args=["2"])
        assert result == 4

    def test_bool(self):
        assert self.new_parser().run(required_bool_arg, args=["--value"]) == True
        assert self.new_parser().run(required_bool_arg, args=["--no-value"]) == False

    def test_bool_true_by_default(self):
        assert self.new_parser().run(bool_default_true, args=["--value"]) == True
        assert self.new_parser().run(bool_default_true, args=["--no-value"]) == False
        assert self.new_parser().run(bool_default_true, args=[]) == True

    def test_bool_false_by_default(self):
        assert self.new_parser().run(bool_default_false, args=["--value"]) == True
        assert self.new_parser().run(bool_default_false, args=["--no-value"]) == False
        assert self.new_parser().run(bool_default_false, args=[]) == False

    def test_from_instance(self):
        instance = Math(rounding=1)
        result = self.new_parser().run(instance, args=["pow", "2", "-e", "2"])
        assert result == 4
        result = self.new_parser().run(instance, args=["add", "1", "1"])
        assert result == 2

    def test_from_method(self):
        instance = Math(rounding=2)
        result = self.new_parser().run(instance.add, args=["1", "1"])
        assert result == 2
        result = self.new_parser().run(instance.pow, args=["2", "-e", "2"])
        assert result == 4

    def test_from_class(self):
        result = self.new_parser().run(Math, args=["pow", "2", "-e", "2"])
        assert result == 4
        result = self.new_parser().run(Math, args=["add", "1", "1"])
        assert result == 2

    def test_custom_command_names(self):
        parser = self.new_parser()
        parser.add_command(Math, name="command1")
        parser.add_command(pow, name="command2")
        with pytest.raises(SystemExit):
            parser.run(args=["pow", "2", "-e", "2"])

        assert parser.run(args=["command2", "2", "-e", "2"]) == 4

import pytest

from interfacy import Interfacy
from interfacy.exceptions import DuplicateCommandError
from tests.fixtures.classes import Math, TextTools
from tests.fixtures.commands import greet, pow


class TestBasicDecorator:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_basic_decorator_registers_function(self, parser: Interfacy):
        """Verify decorator registers a command with the parser."""
        parser.command()(greet)

        assert "greet" in {command.canonical_name for command in parser.get_commands()}
        assert parser.invoke(args=["World"]) == "Hello, World!"

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_decorator_returns_function_unchanged(self, parser: Interfacy):
        """Verify decorated function remains callable independently."""
        decorated = parser.command()(greet)

        assert decorated is greet
        assert decorated("Direct") == "Hello, Direct!"

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_decorator_with_name_override(self, parser: Interfacy):
        """Verify name parameter overrides the function name."""
        parser.command(name="say-hello")(greet)

        assert "say-hello" in {command.cli_name for command in parser.get_commands()}
        assert "greet" not in {command.canonical_name for command in parser.get_commands()}
        assert parser.invoke(args=["World"]) == "Hello, World!"

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_decorator_with_description_override(self, parser: Interfacy):
        """Verify description parameter overrides the docstring."""
        parser.command(description="Custom description")(greet)

        command = parser.get_command_by_cli_name("greet")
        assert command.raw_description == "Custom description"

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_decorator_with_aliases(self, parser: Interfacy):
        """Verify aliases parameter registers alternative command names."""
        parser.command(aliases=["hi", "hey"])(greet)
        parser.command()(pow)

        assert parser.invoke(args=["greet", "World"]) == "Hello, World!"
        assert parser.invoke(args=["hi", "World"]) == "Hello, World!"
        assert parser.invoke(args=["hey", "World"]) == "Hello, World!"

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_decorator_with_pipe_targets(self, parser: Interfacy, mocker):
        """Verify pipe_targets parameter configures stdin piping."""
        parser.command(pipe_targets="name")(greet)

        mocker.patch("interfacy.engine.pipes.read_piped", return_value="Piped")
        assert parser.invoke(args=[]) == "Hello, Piped!"


class TestMultipleDecorators:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_multiple_decorated_functions(self, parser: Interfacy):
        """Verify multiple decorated functions coexist in one parser."""
        parser.command()(greet)
        parser.command()(pow)

        assert parser.invoke(args=["greet", "Alice"]) == "Hello, Alice!"
        assert parser.invoke(args=["pow", "2", "-e", "3"]) == 8

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_mixing_decorator_and_add_command(self, parser: Interfacy):
        """Verify decorator and add_command can be used together."""
        parser.command()(greet)
        parser.add_command(pow)

        assert parser.invoke(args=["greet", "World"]) == "Hello, World!"
        assert parser.invoke(args=["pow", "2", "-e", "3"]) == 8


class TestDecoratorOnClass:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_decorator_on_class(self, parser: Interfacy):
        """Verify decorator works with classes."""
        parser.command()(Math)

        assert "math" in {command.canonical_name for command in parser.get_commands()}
        assert parser.invoke(args=["add", "2", "3"]) == 5

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_decorated_class_returns_class_unchanged(self, parser: Interfacy):
        """Verify decorated class is returned unchanged."""
        decorated = parser.command()(Math)

        assert decorated is Math
        instance = decorated()
        assert instance.add(2, 3) == 5

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_decorator_on_class_with_name_override(self, parser: Interfacy):
        """Verify name override works for classes."""
        parser.command(name="calc")(Math)

        assert "calc" in {command.cli_name for command in parser.get_commands()}
        assert "math" not in {command.canonical_name for command in parser.get_commands()}
        assert parser.invoke(args=["add", "2", "3"]) == 5

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_decorator_on_class_multi_command(self, parser: Interfacy):
        """Verify decorated class works in multi-command context."""
        parser.command()(Math)
        parser.command()(greet)

        assert parser.invoke(args=["math", "add", "2", "3"]) == 5
        assert parser.invoke(args=["greet", "World"]) == "Hello, World!"

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_decorator_supports_per_command_overrides(self, parser: Interfacy):
        """Verify decorator supports per-command registration overrides."""
        parser.command(name="tools", include_classmethods=True)(TextTools)
        parser.command()(greet)
        schema = parser.build_parser_schema()
        subcommands = schema.commands["tools"].subcommands or {}

        assert "tool-name" in subcommands


class TestDecoratorErrors:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_duplicate_decorator_raises_error(self, parser: Interfacy):
        """Verify duplicate command names raise DuplicateCommandError."""
        parser.command(name="duplicate")(greet)

        with pytest.raises(DuplicateCommandError):
            parser.command(name="duplicate")(pow)

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_decorator_conflicts_with_add_command(self, parser: Interfacy):
        """Verify decorator and add_command conflict on same name."""
        parser.add_command(greet)

        with pytest.raises(DuplicateCommandError):
            parser.command(name="greet")(pow)


class TestDecoratorPreservesMetadata:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_decorator_preserves_function_name(self, parser: Interfacy):
        """Verify decorated function retains __name__."""
        expected_name = greet.__name__
        decorated = parser.command()(greet)

        assert decorated.__name__ == expected_name

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_decorator_preserves_function_doc(self, parser: Interfacy):
        """Verify decorated function retains __doc__."""
        expected_doc = greet.__doc__
        decorated = parser.command()(greet)

        assert decorated.__doc__ == expected_doc

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_decorator_preserves_class_name(self, parser: Interfacy):
        """Verify decorated class retains __name__."""
        expected_name = Math.__name__
        decorated = parser.command()(Math)

        assert decorated.__name__ == expected_name

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_decorator_preserves_class_doc(self, parser: Interfacy):
        """Verify decorated class retains __doc__."""
        expected_doc = TextTools.__doc__
        decorated = parser.command()(TextTools)

        assert decorated.__doc__ == expected_doc


class TestDecoratorWithAllParameters:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_decorator_with_all_parameters(self, parser: Interfacy, mocker):
        """Verify decorator works with all parameters combined."""
        mocker.patch("interfacy.engine.pipes.read_piped", return_value=None)

        parser.command(
            name="calculate",
            description="Calculate power",
            aliases=["calc", "c"],
            pipe_targets="base",
        )(pow)
        parser.command()(greet)

        command = parser.get_command_by_cli_name("calculate")
        assert command.raw_description == "Calculate power"

        assert parser.invoke(args=["calculate", "2", "-e", "3"]) == 8
        assert parser.invoke(args=["calc", "2", "-e", "3"]) == 8
        assert parser.invoke(args=["c", "2", "-e", "3"]) == 8

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_decorator_with_pipe_targets_multi_command(self, parser: Interfacy, mocker):
        """Verify pipe_targets work in multi-command context."""
        mocker.patch("interfacy.engine.pipes.read_piped", return_value="3")

        parser.command(name="calculate", pipe_targets="base")(pow)
        parser.command()(greet)

        assert parser.invoke(args=["calculate", "-e", "2"]) == 9

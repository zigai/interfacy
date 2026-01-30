import pytest

from interfacy.core import InterfacyParser
from interfacy.exceptions import DuplicateCommandError
from tests.conftest import Math, TextTools, greet, pow


class TestBasicDecorator:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_basic_decorator_registers_function(self, parser: InterfacyParser):
        """Verify decorator registers a command with the parser."""
        parser.command()(greet)

        assert "greet" in parser.commands
        assert parser.run(args=["World"]) == "Hello, World!"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_decorator_returns_function_unchanged(self, parser: InterfacyParser):
        """Verify decorated function remains callable independently."""
        decorated = parser.command()(greet)

        assert decorated is greet
        assert decorated("Direct") == "Hello, Direct!"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_decorator_with_name_override(self, parser: InterfacyParser):
        """Verify name parameter overrides the function name."""
        parser.command(name="say-hello")(greet)

        assert "say-hello" in parser.commands
        assert "greet" not in parser.commands
        assert parser.run(args=["World"]) == "Hello, World!"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_decorator_with_description_override(self, parser: InterfacyParser):
        """Verify description parameter overrides the docstring."""
        parser.command(description="Custom description")(greet)

        command = parser.commands["greet"]
        assert command.raw_description == "Custom description"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_decorator_with_aliases(self, parser: InterfacyParser):
        """Verify aliases parameter registers alternative command names."""
        parser.command(aliases=["hi", "hey"])(greet)
        parser.command()(pow)

        assert parser.run(args=["greet", "World"]) == "Hello, World!"
        assert parser.run(args=["hi", "World"]) == "Hello, World!"
        assert parser.run(args=["hey", "World"]) == "Hello, World!"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_decorator_with_pipe_targets(self, parser: InterfacyParser, mocker):
        """Verify pipe_targets parameter configures stdin piping."""
        parser.command(pipe_targets="name")(greet)

        mocker.patch("interfacy.core.read_piped", return_value="Piped")
        assert parser.run(args=[]) == "Hello, Piped!"


class TestMultipleDecorators:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_multiple_decorated_functions(self, parser: InterfacyParser):
        """Verify multiple decorated functions coexist in one parser."""
        parser.command()(greet)
        parser.command()(pow)

        assert parser.run(args=["greet", "Alice"]) == "Hello, Alice!"
        assert parser.run(args=["pow", "2", "-e", "3"]) == 8

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_mixing_decorator_and_add_command(self, parser: InterfacyParser):
        """Verify decorator and add_command can be used together."""
        parser.command()(greet)
        parser.add_command(pow)

        assert parser.run(args=["greet", "World"]) == "Hello, World!"
        assert parser.run(args=["pow", "2", "-e", "3"]) == 8


class TestDecoratorOnClass:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_decorator_on_class(self, parser: InterfacyParser):
        """Verify decorator works with classes."""
        parser.command()(Math)

        assert "math" in parser.commands
        assert parser.run(args=["add", "2", "3"]) == 5

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_decorated_class_returns_class_unchanged(self, parser: InterfacyParser):
        """Verify decorated class is returned unchanged."""
        decorated = parser.command()(Math)

        assert decorated is Math
        instance = decorated()
        assert instance.add(2, 3) == 5

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_decorator_on_class_with_name_override(self, parser: InterfacyParser):
        """Verify name override works for classes."""
        parser.command(name="calc")(Math)

        assert "calc" in parser.commands
        assert "math" not in parser.commands
        assert parser.run(args=["add", "2", "3"]) == 5

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_decorator_on_class_multi_command(self, parser: InterfacyParser):
        """Verify decorated class works in multi-command context."""
        parser.command()(Math)
        parser.command()(greet)

        assert parser.run(args=["math", "add", "2", "3"]) == 5
        assert parser.run(args=["greet", "World"]) == "Hello, World!"


class TestDecoratorErrors:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_duplicate_decorator_raises_error(self, parser: InterfacyParser):
        """Verify duplicate command names raise DuplicateCommandError."""
        parser.command(name="duplicate")(greet)

        with pytest.raises(DuplicateCommandError):
            parser.command(name="duplicate")(pow)

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_decorator_conflicts_with_add_command(self, parser: InterfacyParser):
        """Verify decorator and add_command conflict on same name."""
        parser.add_command(greet)

        with pytest.raises(DuplicateCommandError):
            parser.command(name="greet")(pow)


class TestDecoratorPreservesMetadata:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_decorator_preserves_function_name(self, parser: InterfacyParser):
        """Verify decorated function retains __name__."""
        decorated = parser.command()(greet)

        assert decorated.__name__ == "greet"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_decorator_preserves_function_doc(self, parser: InterfacyParser):
        """Verify decorated function retains __doc__."""
        decorated = parser.command()(greet)

        assert decorated.__doc__ == "Return a friendly greeting."

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_decorator_preserves_class_name(self, parser: InterfacyParser):
        """Verify decorated class retains __name__."""
        decorated = parser.command()(Math)

        assert decorated.__name__ == "Math"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_decorator_preserves_class_doc(self, parser: InterfacyParser):
        """Verify decorated class retains __doc__."""
        decorated = parser.command()(TextTools)

        assert decorated.__doc__ == "String utilities with a configurable prefix."


class TestDecoratorWithAllParameters:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_decorator_with_all_parameters(self, parser: InterfacyParser, mocker):
        """Verify decorator works with all parameters combined."""
        mocker.patch("interfacy.core.read_piped", return_value=None)

        parser.command(
            name="calculate",
            description="Calculate power",
            aliases=["calc", "c"],
            pipe_targets="base",
        )(pow)
        parser.command()(greet)

        command = parser.commands["calculate"]
        assert command.raw_description == "Calculate power"

        assert parser.run(args=["calculate", "2", "-e", "3"]) == 8
        assert parser.run(args=["calc", "2", "-e", "3"]) == 8
        assert parser.run(args=["c", "2", "-e", "3"]) == 8

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_decorator_with_pipe_targets_multi_command(self, parser: InterfacyParser, mocker):
        """Verify pipe_targets work in multi-command context."""
        mocker.patch("interfacy.core.read_piped", return_value="3")

        parser.command(name="calculate", pipe_targets="base")(pow)
        parser.command()(greet)

        assert parser.run(args=["calculate", "-e", "2"]) == 9

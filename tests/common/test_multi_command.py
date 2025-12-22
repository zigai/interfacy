import pytest

from interfacy.core import InterfacyParser
from interfacy.exceptions import ConfigurationError, DuplicateCommandError
from tests.conftest import (
    ConcreteProcessor,
    DerivedOperation,
    Empty,
    Math,
    TextTools,
    fn_optional_int,
    fn_str_optional,
    greet,
    pow,
)


class NameOps:
    def say_hello(self, name: str) -> str:
        return f"Hi {name}"


class OrderedOps:
    def first(self) -> str:
        return "first"

    def second(self) -> str:
        return "second"

    def third(self) -> str:
        return "third"


class TestMultipleFunctions:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_two_standalone_functions(self, parser: InterfacyParser):
        """Verify two standalone function commands run independently."""
        parser.add_command(greet)
        parser.add_command(pow)

        assert parser.run(args=["greet", "Ada"]) == "Hello, Ada!"
        assert parser.run(args=["pow", "2", "-e", "3"]) == 8

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_three_or_more_functions(self, parser: InterfacyParser):
        """Verify three or more function commands can be registered and run."""
        parser.add_command(greet)
        parser.add_command(pow)
        parser.add_command(fn_optional_int, name="maybe-int")

        assert parser.run(args=["greet", "Ada"]) == "Hello, Ada!"
        assert parser.run(args=["pow", "3", "-e", "2"]) == 9
        assert parser.run(args=["maybe-int"]) is None

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_functions_with_overlapping_parameter_names(self, parser: InterfacyParser):
        """Verify functions sharing parameter names do not conflict."""
        parser.add_command(greet)
        parser.add_command(fn_str_optional, name="optional-name")

        assert parser.run(args=["greet", "Sam"]) == "Hello, Sam!"
        assert parser.run(args=["optional-name", "--name", "Pat"]) == "Pat"


class TestMultipleClasses:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_two_classes(self, parser: InterfacyParser):
        """Verify two class commands can be registered together."""
        parser.add_command(Math)
        parser.add_command(TextTools)

        assert parser.run(args=["math", "pow", "2", "-e", "2"]) == 4
        assert (
            parser.run(args=["text-tools", "join", "hello", "world", "--sep", " "]) == "hello world"
        )

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_two_instances_same_class_different_names(self, parser: InterfacyParser):
        """Verify two instances of the same class can use distinct names."""
        precise = Math(rounding=6)
        rough = Math(rounding=0)
        parser.add_command(precise, name="math-precise")
        parser.add_command(rough, name="math-rough")

        assert parser.run(args=["math-precise", "add", "1", "2"]) == 3
        assert parser.run(args=["math-rough", "add", "1", "2"]) == 3

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_two_different_class_instances(self, parser: InterfacyParser):
        """Verify commands from different class instances can coexist."""
        math = Math(rounding=2)
        text = TextTools(prefix="hey-")
        parser.add_command(math, name="math-inst")
        parser.add_command(text, name="text-inst")

        assert parser.run(args=["math-inst", "pow", "2", "-e", "2"]) == 4
        assert parser.run(args=["text-inst", "prefix-text", "Ada"]) == "hey-Ada"


class TestComplexMixes:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_function_class_instance_bound_method_mix(self, parser: InterfacyParser):
        """Verify mixed command types work together in one parser."""
        math_instance = Math(rounding=2)
        text_instance = TextTools(prefix="yo-")

        parser.add_command(greet)
        parser.add_command(Math, name="math-class")
        parser.add_command(math_instance, name="math-instance")
        parser.add_command(text_instance.join, name="text-join")

        assert parser.run(args=["greet", "Ada"]) == "Hello, Ada!"
        assert parser.run(args=["math-class", "pow", "2", "-e", "2"]) == 4
        assert parser.run(args=["math-instance", "add", "1", "2"]) == 3
        assert parser.run(args=["text-join", "hi", "there", "--sep", " "]) == "hi there"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_function_and_class_same_method_name(self, parser: InterfacyParser):
        """Verify a function and a class method with the same name both work."""
        parser.add_command(pow)
        parser.add_command(Math)

        assert parser.run(args=["pow", "2", "-e", "3"]) == 8
        assert parser.run(args=["math", "pow", "2", "-e", "3"]) == 8


class TestConflictErrorHandling:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_duplicate_command_name_detection(self, parser: InterfacyParser):
        """Verify duplicate explicit command names raise DuplicateCommandError."""
        parser.add_command(pow, name="dup")
        with pytest.raises(DuplicateCommandError):
            parser.add_command(greet, name="dup")

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_adding_same_function_twice(self, parser: InterfacyParser):
        """Verify adding the same function twice raises DuplicateCommandError."""
        parser.add_command(pow)
        with pytest.raises(DuplicateCommandError):
            parser.add_command(pow)

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_overlapping_aliases(self, parser: InterfacyParser):
        """Verify overlapping aliases across commands raise DuplicateCommandError."""
        parser.add_command(greet, aliases=["hello"])
        with pytest.raises(DuplicateCommandError):
            parser.add_command(pow, aliases=["hello"])

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_alias_conflicts_with_canonical_name(self, parser: InterfacyParser):
        """Verify an alias matching an existing canonical name is rejected."""
        parser.add_command(pow)
        with pytest.raises(DuplicateCommandError):
            parser.add_command(greet, aliases=["pow"])

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_invalid_command_name_in_cli_args(self, parser: InterfacyParser):
        """Verify invalid command names in CLI args error during parsing."""
        parser.add_command(greet)
        parser.add_command(pow)

        with pytest.raises(SystemExit):
            parser.run(args=["nonexistent", "arg"])

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_missing_required_subcommand(self, parser: InterfacyParser):
        """Verify missing required subcommands produce a parse error."""
        parser.add_command(Math)
        with pytest.raises(SystemExit):
            parser.run(args=[])


class TestCommandDiscovery:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_listing_available_commands(self, parser: InterfacyParser):
        """Verify get_commands lists all registered commands."""
        parser.add_command(greet)
        parser.add_command(pow)

        names = {cmd.canonical_name for cmd in parser.get_commands()}
        assert names == {"greet", "pow"}

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_parser_state_before_adding_commands(self, parser: InterfacyParser):
        """Verify parser starts with no commands registered."""
        assert len(parser.commands) == 0

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_transition_single_to_multi_command(self, parser: InterfacyParser):
        """Verify schema transitions from single to multi-command as commands are added."""
        parser.add_command(pow)
        schema = parser.build_parser_schema()
        assert schema.is_multi_command is False

        parser.add_command(greet)
        schema = parser.build_parser_schema()
        assert schema.is_multi_command is True


class TestMethodFiltering:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_private_methods_excluded(self, parser: InterfacyParser):
        """Verify private methods are excluded from subcommands."""
        parser.add_command(TextTools)
        schema = parser.build_parser_schema()
        subcommands = schema.get_command("text-tools").subcommands or {}

        assert "_helper" not in subcommands
        assert "helper" not in subcommands

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_dunder_methods_excluded(self, parser: InterfacyParser):
        """Verify dunder methods are excluded from subcommands."""
        parser.add_command(TextTools)
        schema = parser.build_parser_schema()
        subcommands = schema.get_command("text-tools").subcommands or {}

        assert "__init__" not in subcommands
        assert "__repr__" not in subcommands
        assert "init" not in subcommands
        assert "repr" not in subcommands

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_class_with_no_public_methods(self, parser: InterfacyParser):
        """Verify classes without public methods have no subcommands."""
        parser.add_command(Empty)
        schema = parser.build_parser_schema()
        subcommands = schema.get_command("empty").subcommands or {}

        assert subcommands == {}

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_static_methods_as_subcommands(self, parser: InterfacyParser):
        """Verify static methods are exposed as subcommands."""
        parser.add_command(TextTools)
        schema = parser.build_parser_schema()
        subcommands = schema.get_command("text-tools").subcommands or {}

        assert "repeat" in subcommands

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_class_methods_as_subcommands(self, parser: InterfacyParser):
        """Verify class methods are exposed as subcommands."""
        parser.include_classmethods = True
        parser.add_command(TextTools)
        schema = parser.build_parser_schema()
        subcommands = schema.get_command("text-tools").subcommands or {}

        assert "tool-name" in subcommands

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_properties_not_commands(self, parser: InterfacyParser):
        """Verify properties are not treated as subcommands."""
        parser.add_command(TextTools)
        schema = parser.build_parser_schema()
        subcommands = schema.get_command("text-tools").subcommands or {}

        assert "label" not in subcommands


class TestInheritance:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_inherited_methods_become_subcommands(self, parser: InterfacyParser):
        """Verify inherited methods are included as subcommands."""
        parser.include_inherited_methods = True
        parser.add_command(DerivedOperation)
        schema = parser.build_parser_schema()
        subcommands = schema.get_command("derived-operation").subcommands or {}

        assert "describe" in subcommands

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_overridden_methods(self, parser: InterfacyParser):
        """Verify overridden methods use derived implementations."""
        parser.add_command(DerivedOperation)

        assert parser.run(args=["execute", "3"]) == 6

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_abstract_base_class_methods(self, parser: InterfacyParser):
        """Verify concrete implementations of abstract methods are executable."""
        parser.add_command(ConcreteProcessor)

        assert parser.run(args=["process", "data"]) == "DATA"
        assert parser.run(args=["validate", "data"]) is True


class TestOrderPresentation:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_command_order_in_help(self, parser: InterfacyParser):
        """Verify command order is preserved in help text."""
        parser.add_command(greet)
        parser.add_command(pow)
        parser.add_command(Math)

        help_text = parser.build_parser().format_help()
        assert help_text.index("greet") < help_text.index("pow") < help_text.index("math")

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_subcommand_order_in_help(self, parser: InterfacyParser):
        """Verify subcommand order is preserved in help text."""
        parser.add_command(OrderedOps)

        help_text = parser.build_parser().format_help()
        assert help_text.index("first") < help_text.index("second") < help_text.index("third")


class TestEdgeCases:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_empty_parser_run(self, parser: InterfacyParser):
        """Verify running a parser with no commands returns a ConfigurationError."""
        result = parser.run(args=[])
        assert isinstance(result, ConfigurationError)

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_unicode_in_command_names(self, parser: InterfacyParser):
        """Verify unicode command names can be registered and run."""
        parser.add_command(greet, name="greet-用户")
        parser.add_command(pow)

        assert parser.run(args=["greet-用户", "Ada"]) == "Hello, Ada!"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_very_long_command_names(self, parser: InterfacyParser):
        """Verify very long command names are accepted."""
        long_name = "command-" + ("x" * 60)
        parser.add_command(greet, name=long_name)
        parser.add_command(pow)

        assert parser.run(args=[long_name, "Ada"]) == "Hello, Ada!"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_case_sensitivity(self, parser: InterfacyParser):
        """Verify command names are case-sensitive."""
        parser.add_command(greet, name="Hello")
        parser.add_command(pow, name="hello")

        assert parser.run(args=["Hello", "Ada"]) == "Hello, Ada!"
        assert parser.run(args=["hello", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_numeric_starting_names(self, parser: InterfacyParser):
        """Verify command names starting with digits are accepted."""
        parser.add_command(greet, name="123-command")
        parser.add_command(pow)

        assert parser.run(args=["123-command", "Ada"]) == "Hello, Ada!"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_command_name_looks_like_flag(self, parser: InterfacyParser):
        """Verify command names that resemble flags are accepted."""
        parser.add_command(greet, name="no-prefix")
        parser.add_command(pow)

        assert parser.run(args=["no-prefix", "Ada"]) == "Hello, Ada!"


class TestAliases:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_multiple_aliases_for_one_command(self, parser: InterfacyParser):
        """Verify multiple aliases map to the same command."""
        parser.add_command(greet, aliases=["hi", "hello", "hey"])
        parser.add_command(pow)

        assert parser.run(args=["hi", "Ada"]) == "Hello, Ada!"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_alias_on_class_command(self, parser: InterfacyParser):
        """Verify aliases work for class commands."""
        parser.add_command(Math, aliases=["m"])
        parser.add_command(pow)

        assert parser.run(args=["m", "pow", "2", "-e", "2"]) == 4

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_subcommand_aliases(self, parser: InterfacyParser):
        """Verify method names are translated to CLI-safe subcommands."""
        parser.add_command(NameOps)

        assert parser.run(args=["say-hello", "Ada"]) == "Hi Ada"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_running_command_via_alias(self, parser: InterfacyParser):
        """Verify commands can be invoked via aliases."""
        parser.add_command(greet, aliases=["yo"])
        parser.add_command(pow)

        assert parser.run(args=["yo", "Ada"]) == "Hello, Ada!"


class TestDynamicBehavior:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_adding_commands_after_build_parser_schema(self, parser: InterfacyParser):
        """Verify commands added after schema build are included in later builds."""
        parser.add_command(pow)
        schema = parser.build_parser_schema()
        assert len(schema.commands) == 1

        parser.add_command(greet)
        schema = parser.build_parser_schema()
        assert len(schema.commands) == 2

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_command_specific_description_override(self, parser: InterfacyParser):
        """Verify explicit descriptions override docstrings for commands."""
        parser.add_command(greet, description="Custom greeting")

        command = parser.commands["greet"]
        assert command.raw_description == "Custom greeting"


class TestPipeTargets:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_different_pipe_targets_per_command(self, parser: InterfacyParser, mocker):
        """Verify each command can use its own pipe targets."""
        parser.add_command(greet, pipe_targets="name")
        parser.add_command(pow, pipe_targets="base")

        mocker.patch("interfacy.core.read_piped", side_effect=["Ada", "3"])

        assert parser.run(args=["greet"]) == "Hello, Ada!"
        assert parser.run(args=["pow", "-e", "2"]) == 9

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_pipe_target_on_one_command_only(self, parser: InterfacyParser, mocker):
        """Verify pipe targets apply only to the configured command."""
        parser.add_command(greet)
        parser.add_command(pow, pipe_targets="base")

        mocker.patch("interfacy.core.read_piped", return_value="4")

        assert parser.run(args=["greet", "Ada"]) == "Hello, Ada!"
        assert parser.run(args=["pow", "-e", "2"]) == 16

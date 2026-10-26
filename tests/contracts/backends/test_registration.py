from pathlib import Path
from textwrap import dedent

import pytest

from interfacy import CommandGroup, ExecutableFlag, Interfacy
from interfacy.exceptions import (
    CommandImportError,
    ConfigurationError,
    DuplicateCommandError,
    ReservedFlagError,
    UsageError,
)
from interfacy.introspection.targets import ImportTarget
from tests.fixtures.classes import Math, TextTools
from tests.fixtures.commands import greet, pow


class TestBasicDecorator:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_basic_decorator_registers_function(self, parser: Interfacy):
        """Verify decorator registers a command with the parser."""
        parser.command()(greet)

        assert "greet" in {command.canonical_name for command in parser.get_commands()}
        assert parser.invoke(args=["World"]) == "Hello, World!"

    def test_decorator_returns_function_unchanged(self, schema_parser: Interfacy):
        """Verify decorated function remains callable independently."""
        decorated = schema_parser.command()(greet)

        assert decorated is greet
        assert decorated("Direct") == "Hello, Direct!"

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_decorator_with_name_override(self, parser: Interfacy):
        """Verify name parameter overrides the function name."""
        parser.command(name="say-hello")(greet)

        assert "say-hello" in {command.cli_name for command in parser.get_commands()}
        assert "greet" not in {command.canonical_name for command in parser.get_commands()}
        assert parser.invoke(args=["World"]) == "Hello, World!"

    def test_decorator_with_description_override(self, schema_parser: Interfacy):
        """Verify description parameter overrides the docstring."""
        schema_parser.command(description="Custom description")(greet)

        command = schema_parser.get_command_by_cli_name("greet")
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
    def test_decorator_with_pipe_targets(self, parser: Interfacy, pipe_stdin):
        """Verify pipe_targets parameter configures stdin piping."""
        parser.command(pipe_targets="name")(greet)

        pipe_stdin("Piped")
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

    def test_decorated_class_returns_class_unchanged(self, schema_parser: Interfacy):
        """Verify decorated class is returned unchanged."""
        decorated = schema_parser.command()(Math)

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

    def test_decorator_supports_per_command_overrides(self, schema_parser: Interfacy):
        """Verify decorator supports per-command registration overrides."""
        schema_parser.command(name="tools", include_classmethods=True)(TextTools)
        schema_parser.command()(greet)
        schema = schema_parser.build_parser_schema()
        subcommands = schema.commands["tools"].subcommands or {}

        assert "tool-name" in subcommands


class TestDecoratorErrors:
    def test_duplicate_decorator_raises_error(self, schema_parser: Interfacy):
        """Verify duplicate command names raise DuplicateCommandError."""
        schema_parser.command(name="duplicate")(greet)

        with pytest.raises(DuplicateCommandError):
            schema_parser.command(name="duplicate")(pow)

    def test_decorator_conflicts_with_add_command(self, schema_parser: Interfacy):
        """Verify decorator and add_command conflict on same name."""
        schema_parser.add_command(greet)

        with pytest.raises(DuplicateCommandError):
            schema_parser.command(name="greet")(pow)


class TestDecoratorWithAllParameters:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    @pytest.mark.usefixtures("terminal_stdin")
    def test_decorator_with_all_parameters(self, parser: Interfacy):
        """Verify decorator works with all parameters combined."""
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
    def test_decorator_with_pipe_targets_multi_command(self, parser: Interfacy, pipe_stdin):
        """Verify pipe_targets work in multi-command context."""
        pipe_stdin("3")

        parser.command(name="calculate", pipe_targets="base")(pow)
        parser.command()(greet)

        assert parser.invoke(args=["calculate", "-e", "2"]) == 9


def _write_module(directory: Path, name: str, body: str) -> Path:
    path = directory / f"{name}.py"
    marker = directory / f"{name}.loaded"
    path.write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\n{dedent(body)}",
        encoding="utf-8",
    )

    return path


def _loaded(path: Path) -> bool:
    return path.with_suffix(".loaded").exists()


_GREETING_MODULE = '''
def greet(name: str) -> str:
    """Return a friendly greeting."""
    return f"Hello, {name}!"
'''

_OPS_MODULE = """
from interfacy import CommandGroup


def add(a: int, b: int) -> int:
    return a + b


def create_group() -> CommandGroup:
    group = CommandGroup("ops", description="Arithmetic operations", aliases=("o",))
    group.add_command(add)
    return group
"""


@pytest.fixture(params=["argparse", "click"])
def lazy_parser(request: pytest.FixtureRequest) -> Interfacy:
    return Interfacy(backend=request.param, print_result=False, sys_exit_enabled=False)


class TestImportPathRegistration:
    def test_root_help_imports_nothing_and_matches_eager_help(
        self, lazy_parser: Interfacy, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        greeting = _write_module(tmp_path, "greeting", _GREETING_MODULE)
        ops = _write_module(tmp_path, "ops", _OPS_MODULE)
        lazy_parser.add_command(f"{greeting}:greet")
        lazy_parser.add_group(f"{ops}:create_group")

        lazy_parser.invoke(args=["--help"])
        lazy_help = capsys.readouterr().out

        assert not _loaded(greeting)
        assert not _loaded(ops)

        eager = Interfacy(backend=lazy_parser.backend, print_result=False)
        eager.add_command(ImportTarget(str(greeting), "greet").load())
        eager.add_group(ImportTarget(str(ops), "create_group").load()())
        eager.invoke(args=["--help"])

        assert lazy_help == capsys.readouterr().out

    def test_selected_command_imports_only_its_target(self, lazy_parser: Interfacy, tmp_path: Path):
        greeting = _write_module(tmp_path, "greeting", _GREETING_MODULE)
        ops = _write_module(tmp_path, "ops", _OPS_MODULE)
        lazy_parser.add_command(f"{greeting}:greet")
        lazy_parser.add_group(f"{ops}:create_group")

        assert lazy_parser.invoke(args=["o", "add", "2", "3"]) == 5
        assert _loaded(ops)
        assert not _loaded(greeting)

    def test_unknown_command_imports_nothing(self, lazy_parser: Interfacy, tmp_path: Path):
        greeting = _write_module(tmp_path, "greeting", _GREETING_MODULE)
        lazy_parser.add_command(f"{greeting}:greet")
        lazy_parser.add_command(pow)

        with pytest.raises(UsageError):
            lazy_parser.invoke(args=["missing"])

        assert not _loaded(greeting)

    def test_single_registered_path_runs_without_a_command_name(
        self, lazy_parser: Interfacy, tmp_path: Path
    ):
        greeting = _write_module(tmp_path, "greeting", _GREETING_MODULE)
        lazy_parser.add_command(f"{greeting}:greet")

        assert lazy_parser.invoke(args=["World"]) == "Hello, World!"

    def test_import_failure_affects_only_its_command(self, lazy_parser: Interfacy, tmp_path: Path):
        broken = _write_module(
            tmp_path,
            "broken",
            '''
            raise RuntimeError("cannot import")

            def broken() -> None:
                """Broken command."""
            ''',
        )
        lazy_parser.add_command(f"{broken}:broken")
        lazy_parser.add_command(greet)

        assert lazy_parser.invoke(args=["greet", "World"]) == "Hello, World!"

        with pytest.raises(CommandImportError, match="cannot import"):
            lazy_parser.invoke(args=["broken"])

    def test_non_literal_name_requires_explicit_name_and_description(
        self, lazy_parser: Interfacy, tmp_path: Path
    ):
        module = _write_module(
            tmp_path,
            "dynamic",
            """
            from interfacy import CommandGroup

            NAME = "dynamic"

            def create() -> CommandGroup:
                group = CommandGroup(NAME, description=NAME.title())
                group.add_command(len)
                return group
            """,
        )

        with pytest.raises(ConfigurationError, match="name="):
            lazy_parser.add_group(f"{module}:create")

        lazy_parser.add_group(f"{module}:create", name="dyn", description="Dynamic commands")
        lazy_parser.add_command(greet)

        assert lazy_parser.get_command_by_cli_name("dyn").raw_description == "Dynamic commands"
        assert not _loaded(module)

    def test_missing_symbol_fails_at_registration(self, lazy_parser: Interfacy, tmp_path: Path):
        greeting = _write_module(tmp_path, "greeting", _GREETING_MODULE)

        with pytest.raises(ConfigurationError, match="missing"):
            lazy_parser.add_command(f"{greeting}:missing")

    def test_path_and_object_with_the_same_name_conflict(
        self, lazy_parser: Interfacy, tmp_path: Path
    ):
        greeting = _write_module(tmp_path, "greeting", _GREETING_MODULE)
        lazy_parser.add_command(greet)

        with pytest.raises(DuplicateCommandError):
            lazy_parser.add_command(f"{greeting}:greet")

    def test_build_parser_schema_imports_every_target(self, lazy_parser: Interfacy, tmp_path: Path):
        greeting = _write_module(tmp_path, "greeting", _GREETING_MODULE)
        ops = _write_module(tmp_path, "ops", _OPS_MODULE)
        lazy_parser.add_command(f"{greeting}:greet")
        lazy_parser.add_group(f"{ops}:create_group")

        schema = lazy_parser.build_parser_schema()

        assert _loaded(greeting)
        assert _loaded(ops)
        assert all(command.command_type != "deferred" for command in schema.commands.values())

    def test_argument_file_before_the_command_can_select_a_path_target(self, tmp_path: Path):
        greeting = _write_module(tmp_path, "greeting", _GREETING_MODULE)
        args_file = tmp_path / "greet.args"
        args_file.write_text("greet\nWorld\n", encoding="utf-8")
        parser = Interfacy(print_result=False, allow_args_from_file=True)
        parser.add_command(f"{greeting}:greet")
        parser.add_command(pow)

        assert parser.invoke(args=[f"@{args_file}"]) == "Hello, World!"

    def test_single_path_help_imports_the_target_and_shows_its_parameters(
        self, lazy_parser: Interfacy, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        greeting = _write_module(tmp_path, "greeting", _GREETING_MODULE)
        lazy_parser.add_command(f"{greeting}:greet")

        lazy_parser.invoke(args=["--help"])

        assert _loaded(greeting)
        assert "NAME" in capsys.readouterr().out

    def test_root_executable_flag_does_not_import_unresolved_entries(
        self, lazy_parser: Interfacy, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        greeting = _write_module(tmp_path, "greeting", _GREETING_MODULE)
        ops = _write_module(tmp_path, "ops", _OPS_MODULE)
        lazy_parser.apply_setup(executable_flags=[ExecutableFlag("--version", lambda: "1.2.3")])
        lazy_parser.add_command(f"{greeting}:greet")
        lazy_parser.add_group(f"{ops}:create_group")

        lazy_parser.invoke(args=["--version", "ops", "add", "2", "3"])

        assert "1.2.3" in capsys.readouterr().out
        assert not _loaded(greeting)
        assert not _loaded(ops)

    def test_build_parser_for_completion_resolves_every_target(
        self, lazy_parser: Interfacy, tmp_path: Path
    ) -> None:
        greeting = _write_module(tmp_path, "greeting", _GREETING_MODULE)
        ops = _write_module(tmp_path, "ops", _OPS_MODULE)
        lazy_parser.add_command(f"{greeting}:greet")
        lazy_parser.add_group(f"{ops}:create_group")

        lazy_parser.build_parser()

        assert _loaded(greeting)
        assert _loaded(ops)

    def test_object_group_schema_is_built_only_when_selected(
        self, lazy_parser: Interfacy, capsys: pytest.CaptureFixture[str]
    ) -> None:
        def reserved(help: int) -> None:
            pass

        group = CommandGroup("broken", description="Reserved argument name.")
        group.add_command(reserved)
        lazy_parser.add_group(group)
        lazy_parser.add_command(greet)

        lazy_parser.invoke(args=["--help"])
        assert "broken" in capsys.readouterr().out
        assert lazy_parser.invoke(args=["greet", "World"]) == "Hello, World!"

        with pytest.raises(ReservedFlagError):
            lazy_parser.invoke(args=["broken", "--help"])

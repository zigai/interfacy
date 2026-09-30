import pytest
from objinspect import Method, inspect
from pytest_mock import MockerFixture
from strto import StrToTypeParser

from interfacy.naming.name_mapping import NameMapping
from interfacy.runtime.context import ExecutionContext
from interfacy.runtime.runner import SchemaRunner
from interfacy.schema.builder import ParserSchemaBuilder
from tests.unit.schema.conftest import SchemaSource


class Calculator:
    factor: int

    def __init__(self, factor: int = 2) -> None:
        self.factor = factor

    def multiply(self, value: int) -> int:
        return value * self.factor


@pytest.fixture
def schema_builder() -> ParserSchemaBuilder:
    source = SchemaSource()
    return ParserSchemaBuilder(source.schema_context())


@pytest.fixture
def execution_context() -> ExecutionContext:
    return ExecutionContext(
        commands={},
        argument_names=NameMapping(lambda x: x),
        command_names=NameMapping(lambda x: x),
        type_parser=StrToTypeParser(),
        schema=None,
        read_piped_input=lambda: None,
        resolve_pipe_targets=lambda _cmd, _sub: None,
        parameters_for=lambda _cmd, _sub: {},
    )


class TestParserSchemaBuilderMethodDispatch:
    """Verify that ParserSchemaBuilder.build_command_spec_for dispatches Method to method_command."""

    def test_unbound_method_dispatches_to_method_command_with_initializer(
        self, schema_builder: ParserSchemaBuilder
    ) -> None:
        unbound_method = Method(Calculator.multiply, Calculator)

        cmd = schema_builder.build_command_spec_for(unbound_method, canonical_name="multiply")

        assert [arg.name for arg in cmd.initializer] == ["factor"]
        assert [arg.name for arg in cmd.parameters] == ["value"]

    def test_bound_method_dispatches_to_method_command_without_initializer(
        self, schema_builder: ParserSchemaBuilder
    ) -> None:
        calc = Calculator(factor=5)
        bound_method = inspect(calc.multiply)
        assert isinstance(bound_method, Method)

        cmd = schema_builder.build_command_spec_for(bound_method, canonical_name="multiply")

        assert cmd.initializer == []
        assert [arg.name for arg in cmd.parameters] == ["value"]

    def test_method_command_is_invoked_instead_of_function_command(
        self, schema_builder: ParserSchemaBuilder, mocker: MockerFixture
    ) -> None:
        calc = Calculator()
        bound_method = inspect(calc.multiply)

        spy_method = mocker.spy(schema_builder.commands, "method_command")
        spy_func = mocker.spy(schema_builder.commands, "function_command")

        _ = schema_builder.build_command_spec_for(bound_method, canonical_name="multiply")

        assert spy_method.call_count == 1
        assert spy_func.call_count == 0


class TestSchemaRunnerMethodDispatch:
    """Verify that SchemaRunner.run_command dispatches Method objects to run_method."""

    def test_run_command_dispatches_unbound_method_to_run_method(
        self, schema_builder: ParserSchemaBuilder, execution_context: ExecutionContext
    ) -> None:
        unbound_method = Method(Calculator.multiply, Calculator)
        cmd = schema_builder.build_command_spec_for(unbound_method, canonical_name="multiply")

        runner = SchemaRunner(namespace={}, context=execution_context, args=[])
        result = runner.run_command(cmd, {"factor": 4, "value": 3})

        assert result == 12

    def test_run_command_dispatches_bound_method_to_run_method(
        self, schema_builder: ParserSchemaBuilder, execution_context: ExecutionContext
    ) -> None:
        calc = Calculator(factor=10)
        bound_method = inspect(calc.multiply)
        cmd = schema_builder.build_command_spec_for(bound_method, canonical_name="multiply")

        runner = SchemaRunner(namespace={}, context=execution_context, args=[])
        result = runner.run_command(cmd, {"value": 5})

        assert result == 50

    def test_run_method_invoked_instead_of_run_function(
        self,
        schema_builder: ParserSchemaBuilder,
        execution_context: ExecutionContext,
        mocker: MockerFixture,
    ) -> None:
        calc = Calculator()
        bound_method = inspect(calc.multiply)
        cmd = schema_builder.build_command_spec_for(bound_method, canonical_name="multiply")

        runner = SchemaRunner(namespace={}, context=execution_context, args=[])
        spy_run_method = mocker.spy(runner, "run_method")
        spy_run_func = mocker.spy(runner, "run_function")

        result = runner.run_command(cmd, {"value": 7})

        assert result == 14
        assert spy_run_method.call_count == 1
        assert spy_run_func.call_count == 0

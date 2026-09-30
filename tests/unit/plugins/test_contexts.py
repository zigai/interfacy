from typing import Any

import pytest

from interfacy import Interfacy
from interfacy.plugins import (
    ArgumentDescriptor,
    ArgumentRef,
    BeforeParseContext,
    ExecuteContext,
    InterfacyPlugin,
    SchemaDescriptor,
)


def argument_descriptor() -> ArgumentDescriptor:
    return ArgumentDescriptor(
        command_path=("command",),
        name="value",
        display_name="value",
        kind="option",
        value_shape="single",
        flags=("--value",),
        required=True,
        type=str,
    )


@pytest.fixture
def schema() -> SchemaDescriptor:
    return SchemaDescriptor(None, None, (("command",),), (argument_descriptor(),))


def test_equivalent_argument_refs_retrieve_recovery_values(schema: SchemaDescriptor) -> None:
    argument = schema.arguments[0]
    ref = ArgumentRef(("command",), "value", argument)
    values = {ref: "provided"}

    assert values[ArgumentRef(("command",), "value", argument_descriptor())] == "provided"


def test_context_construction_copies_and_freezes_container_inputs() -> None:
    args = ["value"]
    nested = ["original"]
    context = BeforeParseContext("argparse", {"nested": nested}, args)

    args.append("later")
    nested.append("later")

    assert context.args == ("value",)
    assert context.metadata["nested"] == ("original",)

    with pytest.raises(TypeError):
        context.metadata["changed"] = True


def test_execution_context_rebinding_does_not_change_command_arguments() -> None:
    seen: list[str] = []

    class Outer(InterfacyPlugin):
        def wrap_execute(self, context: ExecuteContext, call_next) -> Any:
            context.namespace = {"value": "replaced"}
            return call_next()

    class Inner(InterfacyPlugin):
        def wrap_execute(self, context: ExecuteContext, call_next) -> Any:
            seen.append(context.namespace["value"])
            return call_next()

    def command(value: str) -> str:
        return value

    parser = Interfacy(plugins=[Outer(), Inner()])

    assert parser.invoke(command, args=["original"]) == "original"
    assert seen == ["replaced"]

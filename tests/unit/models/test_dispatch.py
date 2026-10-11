from dataclasses import InitVar, dataclass, field
from typing import ClassVar

import pytest

from interfacy import Interfacy
from interfacy.models import (
    build_model_instance,
    coerce_model_value,
    is_model_type,
    model_fields_for_expansion,
    model_instance_to_values,
)
from tests.fixtures.models import Address, UserWithAddress


def test_optional_empty_nested_dict_becomes_none() -> None:
    user = build_model_instance(
        UserWithAddress,
        {"name": "Ada", "age": 32, "address": {}},
    )

    assert user == UserWithAddress(name="Ada", age=32, address=None)


def test_required_empty_nested_dict_is_not_optional() -> None:
    with pytest.raises(TypeError):
        coerce_model_value(Address, {})


def test_nested_dataclass_values_round_trip() -> None:
    user = UserWithAddress(name="Ada", age=32, address=Address(city="Austin", zip=78701))

    values = model_instance_to_values(UserWithAddress, user)

    assert values == {"name": "Ada", "age": 32, "address": {"city": "Austin", "zip": 78701}}
    assert build_model_instance(UserWithAddress, values) == user


def test_non_model_values_are_returned_unchanged() -> None:
    values = {"value": 1}

    assert build_model_instance(int, values) is values
    assert is_model_type(int) is False


@dataclass
class InitializedModel:
    name: str
    count: InitVar[int]
    label: str = field(init=False)
    category: ClassVar[str] = "generic"

    def __post_init__(self, count: int) -> None:
        self.label = self.name * count


@dataclass
class DefaultInitializedModel:
    name: str
    count: InitVar[int] = 2
    label: str = field(init=False)

    def __post_init__(self, count: int) -> None:
        self.label = self.name * count


@pytest.mark.parametrize("model_type", [InitializedModel, DefaultInitializedModel])
def test_dataclass_initvar_discovery_uses_inner_annotation(model_type: type) -> None:
    fields = model_fields_for_expansion(model_type)

    assert [(item.name, item.annotation) for item in fields] == [("name", str), ("count", int)]
    assert fields[1].required is (model_type is InitializedModel)


@pytest.mark.parametrize("model_type", [InitializedModel, DefaultInitializedModel])
def test_dataclass_initvar_reconstruction_runs_post_init(model_type: type) -> None:
    result = build_model_instance(model_type, {"name": "x", "count": 3})

    assert result.label == "xxx"


@pytest.mark.parametrize("backend", ["argparse", "click"])
@pytest.mark.parametrize("model_type", [InitializedModel, DefaultInitializedModel])
def test_dataclass_initvar_cli_reaches_post_init(backend: str, model_type: type) -> None:
    def command(model: model_type) -> str:
        return model.label

    parser = Interfacy(backend=backend)

    assert parser.invoke(command, args=["--model.name", "x", "--model.count", "3"]) == "xxx"

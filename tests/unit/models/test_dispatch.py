import pytest

from interfacy.models import (
    build_model_instance,
    coerce_model_value,
    is_model_type,
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

from typing import Any

import pytest

from interfacy.common.sentinels import MODEL_DEFAULT_UNSET
from interfacy.runtime.models import (
    ExpandedModelValidationError,
    group_expanded_arguments,
    reconstruct_expanded_models,
)
from interfacy.schema.model import Argument, ArgumentDefault, ArgumentKind, ValueShape
from interfacy.schema.values import ValueCardinality
from tests.fixtures.models import Address, UserWithAddress


def expanded_argument(
    *path: str,
    model_default: Any = MODEL_DEFAULT_UNSET,
    parent_is_optional: bool = False,
) -> Argument:
    name = ".".join(path)
    return Argument(
        name=name,
        display_name=name,
        kind=ArgumentKind.OPTION,
        value_shape=ValueShape.SINGLE,
        flags=(f"--{name}",),
        required=False,
        cardinality=ValueCardinality(1, 1, 1),
        argument_default=ArgumentDefault.absent(),
        help=None,
        type=None,
        parser=None,
        is_expanded_from=path[0],
        expansion_path=path,
        original_model_type=UserWithAddress,
        parent_is_optional=parent_is_optional,
        model_default=model_default,
    )


def user_arguments(**options: Any) -> list[Argument]:
    return [
        expanded_argument("user", "name", **options),
        expanded_argument("user", "age", **options),
        expanded_argument("user", "address", "city", **options),
        expanded_argument("user", "address", "zip", **options),
    ]


def test_reconstructs_nested_model_and_removes_flat_values() -> None:
    args = {
        "user.name": "Ada",
        "user.age": 32,
        "user.address.city": "Austin",
        "user.address.zip": 78701,
        "other": 1,
    }

    result = reconstruct_expanded_models(args, user_arguments())

    assert result == {
        "user": UserWithAddress(name="Ada", age=32, address=Address(city="Austin", zip=78701)),
        "other": 1,
    }


def test_provided_nested_model_reports_missing_fields_with_context() -> None:
    args = {"user.name": "Ada", "user.age": 32, "user.address.city": "Austin"}

    with pytest.raises(ExpandedModelValidationError) as error:
        reconstruct_expanded_models(args, user_arguments())

    assert error.value.message == (
        "the following arguments are required when --user.address.city is provided: "
        "--user.address.zip"
    )


def test_unprovided_model_uses_declared_default() -> None:
    default = UserWithAddress(name="Grace", age=40)

    result = reconstruct_expanded_models({}, user_arguments(model_default=default))

    assert result == {"user": default}


def test_unprovided_optional_model_becomes_none() -> None:
    result = reconstruct_expanded_models({}, user_arguments(parent_is_optional=True))

    assert result == {"user": None}


def test_provided_fields_merge_over_declared_default() -> None:
    default = UserWithAddress(name="Grace", age=40, address=Address(city="Austin", zip=78701))

    result = reconstruct_expanded_models(
        {"user.address.city": "Boston"},
        user_arguments(model_default=default),
    )

    assert result == {
        "user": UserWithAddress(name="Grace", age=40, address=Address(city="Boston", zip=78701))
    }


def test_groups_only_expanded_arguments() -> None:
    arguments = user_arguments()
    plain = expanded_argument("plain")
    plain.is_expanded_from = None

    assert group_expanded_arguments([*arguments, plain]) == {"user": arguments}

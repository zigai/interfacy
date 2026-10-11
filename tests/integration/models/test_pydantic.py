from pathlib import Path

import pydantic.v1
import pytest
from pydantic import AliasChoices, AliasPath, BaseModel, Field, ValidationError
from pydantic.v1 import BaseModel as LegacyBaseModel
from pydantic.v1 import Field as LegacyField

from interfacy import Interfacy
from interfacy.models import build_model_instance


class Address(BaseModel):
    city: str


class User(BaseModel):
    name: str
    age: int = Field(ge=0)
    address: Address | None = None
    tags: list[str] = Field(default_factory=list)


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_pydantic_model_reconstructs_required_nested_and_repeated_fields(backend: str) -> None:
    def command(user: User) -> User:
        return user

    parser = Interfacy(backend=backend)
    parser.add_command(command)

    result = parser.invoke(
        args=[
            "--user.name",
            "Ada",
            "--user.age",
            "32",
            "--user.address.city",
            "Ljubljana",
            "--user.tags",
            "cli",
            "python",
        ]
    )

    assert result == User(
        name="Ada",
        age=32,
        address=Address(city="Ljubljana"),
        tags=["cli", "python"],
    )


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_pydantic_model_validation_prevents_command_side_effects(
    backend: str,
    tmp_path: Path,
) -> None:
    sentinel = tmp_path / "executed"

    def command(user: User) -> User:
        sentinel.write_text(user.name, encoding="utf-8")
        return user

    parser = Interfacy(backend=backend)

    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        parser.invoke(command, args=["--user.name", "Ada", "--user.age", "-1"])

    assert not sentinel.exists()


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_pydantic_default_factory_is_fresh_across_invocations(backend: str) -> None:
    def command(user: User) -> User:
        return user

    parser = Interfacy(backend=backend)

    first = parser.invoke(command, args=["--user.name", "Ada", "--user.age", "32"])
    first.tags.append("mutated")
    second = parser.invoke(command, args=["--user.name", "Grace", "--user.age", "37"])

    assert first.tags == ["mutated"]
    assert second.tags == []
    assert second.address is None


@pytest.mark.parametrize("backend", ["argparse", "click"])
@pytest.mark.parametrize(
    ("model_base", "field_factory"),
    [(BaseModel, Field), (pydantic.v1.BaseModel, pydantic.v1.Field)],
)
def test_excluded_default_field_survives_an_unrelated_cli_override(
    backend: str,
    model_base: type,
    field_factory,
) -> None:
    class Config(model_base):
        destination: str = field_factory(default="fallback", exclude=True)
        count: int = 0

    default = Config(destination="chosen")

    def command(config: Config = default) -> tuple[str, int]:
        return config.destination, config.count

    assert Interfacy(backend=backend).invoke(command, args=["--config.count", "1"]) == ("chosen", 1)
    assert (default.destination, default.count) == ("chosen", 0)


class AliasedAddress(BaseModel):
    city: str = Field(alias="town")


class AliasedUser(BaseModel):
    name: str = Field(alias="display_name")
    age: int = Field(default=1, alias="years", ge=0)
    address: AliasedAddress = Field(alias="location")
    model_config = {"extra": "forbid", "serialize_by_alias": True}


class LegacyAliasedAddress(LegacyBaseModel):
    city: str = LegacyField(alias="town")


class LegacyAliasedUser(LegacyBaseModel):
    name: str = LegacyField(alias="display_name")
    age: int = LegacyField(default=1, alias="years", ge=0)
    address: LegacyAliasedAddress = LegacyField(alias="location")


@pytest.mark.parametrize("backend", ["argparse", "click"])
@pytest.mark.parametrize("model_type", [AliasedUser, LegacyAliasedUser])
def test_pydantic_aliases_reconstruct_nested_fields(backend: str, model_type: type) -> None:
    def command(user: model_type) -> model_type:
        return user

    result = Interfacy(backend=backend).invoke(
        command,
        args=["--user.name", "Ada", "--user.age", "3", "--user.address.city", "Oslo"],
    )

    assert (result.name, result.age, result.address.city) == ("Ada", 3, "Oslo")


@pytest.mark.parametrize("backend", ["argparse", "click"])
@pytest.mark.parametrize("model_type", [AliasedUser, LegacyAliasedUser])
def test_pydantic_aliases_update_default_instance(backend: str, model_type: type) -> None:
    default = model_type(display_name="Ada", years=2, location={"town": "Oslo"})

    def command(user: model_type = default) -> model_type:
        return user

    result = Interfacy(backend=backend).invoke(
        command, args=["--user.age", "4", "--user.address.city", "Lima"]
    )

    assert (result.name, result.age, result.address.city) == ("Ada", 4, "Lima")
    assert (default.age, default.address.city) == (2, "Oslo")


@pytest.mark.parametrize(
    "alias",
    [
        "",
        "input_count",
        AliasChoices("", "input_count"),
        AliasPath("payload", "count"),
        AliasPath("payload", 1, "count"),
        AliasPath("payload", -1, "count"),
        AliasChoices("input_count", AliasPath("payload", "count")),
        AliasChoices(AliasPath("payload", "count"), "input_count"),
    ],
)
@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_pydantic_validation_aliases_preserve_validation(alias: object, backend: str) -> None:
    class ValidatedModel(BaseModel):
        count: int = Field(default=1, alias="output_count", validation_alias=alias, ge=0)

    def command(model: ValidatedModel) -> ValidatedModel:
        return model

    parser = Interfacy(backend=backend)

    assert parser.invoke(command, args=["--model.count", "3"]).count == 3
    with pytest.raises(ValidationError):
        parser.invoke(command, args=["--model.count", "-1"])


class EmptyAliasModel(BaseModel):
    count: int = Field(alias="")


class LegacyEmptyAliasModel(LegacyBaseModel):
    count: int = LegacyField(alias="")


@pytest.mark.parametrize("backend", ["argparse", "click"])
@pytest.mark.parametrize("model_type", [EmptyAliasModel, LegacyEmptyAliasModel])
def test_pydantic_empty_field_alias_preserves_input(backend: str, model_type: type) -> None:
    def command(model: model_type) -> model_type:
        return model

    assert Interfacy(backend=backend).invoke(command, args=["--model.count", "3"]).count == 3


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_pydantic_negative_alias_stays_relative_to_final_list(backend: str) -> None:
    class SharedModel(BaseModel):
        first: int = Field(default=0, validation_alias=AliasPath("payload", -2, "value"))
        second: int = Field(default=0, validation_alias=AliasPath("payload", 2, "value"))

    def command(model: SharedModel) -> SharedModel:
        return model

    result = Interfacy(backend=backend).invoke(
        command, args=["--model.first", "1", "--model.second", "2"]
    )

    assert (result.first, result.second) == (1, 2)


@pytest.mark.parametrize("backend", ["argparse", "click"])
@pytest.mark.parametrize(
    ("first_alias", "second_alias"),
    [
        ("shared", "shared"),
        (AliasPath("payload", -1, "value"), AliasPath("payload", 2, "value")),
    ],
)
def test_pydantic_conflicting_alias_values_do_not_execute(
    backend: str, first_alias: str | AliasPath, second_alias: str | AliasPath
) -> None:
    class SharedModel(BaseModel):
        first: int = Field(default=0, validation_alias=first_alias)
        second: int = Field(default=0, validation_alias=second_alias)

    executed: list[tuple[int, int]] = []

    def command(model: SharedModel) -> None:
        executed.append((model.first, model.second))

    with pytest.raises(ValueError, match="Conflicting Pydantic validation alias paths"):
        Interfacy(backend=backend).invoke(
            command, args=["--model.first", "1", "--model.second", "2"]
        )

    assert executed == []


def test_pydantic_equal_validation_alias_values_are_preserved() -> None:
    class SharedModel(BaseModel):
        first: int = Field(validation_alias="shared")
        second: int = Field(validation_alias="shared")

    result = build_model_instance(SharedModel, {"first": 1, "second": 1})

    assert (result.first, result.second) == (1, 1)


def test_pydantic_shared_validation_alias_paths() -> None:
    class SharedModel(BaseModel):
        first: int = Field(validation_alias=AliasPath("payload", 0, "value"))
        second: int = Field(validation_alias=AliasPath("payload", 1, "value"))

    result = build_model_instance(SharedModel, {"first": 2, "second": 3})

    assert (result.first, result.second) == (2, 3)


def test_pydantic_disabled_alias_validation_uses_field_names() -> None:
    class NameModel(BaseModel):
        count: int = Field(alias="input_count", ge=0)
        model_config = {"validate_by_alias": False, "validate_by_name": True}

    assert build_model_instance(NameModel, {"count": 3}).count == 3
    with pytest.raises(ValidationError):
        build_model_instance(NameModel, {"count": -1})

from pathlib import Path

import pytest
from pydantic import BaseModel, Field, ValidationError

from interfacy import Interfacy


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

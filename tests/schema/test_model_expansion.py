from dataclasses import dataclass

import pytest
from objinspect import Function

from interfacy.appearance.layouts import InterfacyLayout
from interfacy.argparse_backend.argparser import Argparser
from interfacy.schema.builder import ParserSchemaBuilder
from tests.schema.conftest import (
    Address,
    FakeParser,
    UserWithAddress,
    greet_with_address,
    greet_plain,
    greet_plain_default,
    greet_plain_with_address,
    maybe_plain,
    uses_levels,
)


@dataclass
class User:
    name: str
    age: int


def greet(user: User) -> str:
    return f"Hello {user.name}, age {user.age}"


def maybe_user(user: User | None = None) -> User | None:
    return user


def test_schema_expands_dataclass_fields(builder_parser: FakeParser) -> None:
    builder_parser.register_command(Function(greet), canonical_name="greet")
    builder = ParserSchemaBuilder(builder_parser)
    schema = builder.build()

    cmd = schema.commands["greet"]
    names = {arg.name for arg in cmd.parameters}
    flags = {arg.flags[0] for arg in cmd.parameters}

    assert "user.name" in names
    assert "user.age" in names
    assert "--user.name" in flags
    assert "--user.age" in flags


def test_argparse_reconstructs_expanded_dataclass() -> None:
    parser = Argparser(sys_exit_enabled=False)
    result = parser.run(greet, args=["--user.name", "Alice", "--user.age", "30"])
    assert result == "Hello Alice, age 30"


def test_argparse_reconstructs_nested_dataclass() -> None:
    parser = Argparser(sys_exit_enabled=False)
    result = parser.run(
        greet_with_address,
        args=[
            "--user.name",
            "Alice",
            "--user.age",
            "30",
            "--user.address.city",
            "Austin",
            "--user.address.zip",
            "78701",
        ],
    )
    assert result == "Hello Alice, age 30 from Austin 78701"


def test_optional_model_none_when_no_flags() -> None:
    parser = Argparser(sys_exit_enabled=False)
    result = parser.run(maybe_user, args=[])
    assert result is None


def test_optional_nested_fields_are_not_required(builder_parser: FakeParser) -> None:
    builder_parser.register_command(
        Function(greet_with_address), canonical_name="greet-with-address"
    )
    builder = ParserSchemaBuilder(builder_parser)
    schema = builder.build()

    cmd = schema.commands["greet-with-address"]
    required_by_name = {arg.name: arg.required for arg in cmd.parameters}

    assert required_by_name["user.name"] is True
    assert required_by_name["user.age"] is True
    assert required_by_name["user.address.city"] is False
    assert required_by_name["user.address.zip"] is False


DEFAULT_USER = UserWithAddress(
    name="Tess",
    age=40,
    address=Address(city="Austin", zip=78701),
)


def greet_default(user: UserWithAddress = DEFAULT_USER) -> str:
    return greet_with_address(user)


def test_model_default_used_when_no_flags() -> None:
    parser = Argparser(sys_exit_enabled=False)
    result = parser.run(greet_default, args=[])
    assert result == "Hello Tess, age 40 from Austin 78701"


def test_model_default_merged_with_overrides() -> None:
    parser = Argparser(sys_exit_enabled=False)
    result = parser.run(greet_default, args=["--user.age", "41"])
    assert result == "Hello Tess, age 41 from Austin 78701"


def test_expanded_fields_optional_when_model_default_present(builder_parser: FakeParser) -> None:
    builder_parser.register_command(Function(greet_default), canonical_name="greet-default")
    builder = ParserSchemaBuilder(builder_parser)
    schema = builder.build()

    cmd = schema.commands["greet-default"]
    required_by_name = {arg.name: arg.required for arg in cmd.parameters}
    assert required_by_name["user.name"] is False
    assert required_by_name["user.age"] is False


def test_model_expansion_respects_max_depth() -> None:
    parser = FakeParser(model_expansion_max_depth=2)
    parser.register_command(Function(uses_levels), canonical_name="uses-levels")
    builder = ParserSchemaBuilder(parser)
    schema = builder.build()

    cmd = schema.commands["uses-levels"]
    names = {arg.name for arg in cmd.parameters}

    assert "level1.level2.level3" in names
    assert "level1.level2.level3.leaf" not in names


def test_docstring_help_used_for_dataclass_fields() -> None:
    parser = FakeParser(help_layout=InterfacyLayout())
    parser.register_command(Function(greet_with_address), canonical_name="greet-docs")
    builder = ParserSchemaBuilder(parser)
    schema = builder.build()

    cmd = schema.commands["greet-docs"]
    help_text = {arg.name: arg.help or "" for arg in cmd.parameters}

    assert "Display name." in help_text["user.name"]
    assert "Age in years." in help_text["user.age"]
    assert "City name." in help_text["user.address.city"]
    assert "Postal or ZIP code." in help_text["user.address.zip"]


def test_help_output_contains_expanded_flags() -> None:
    parser = Argparser(sys_exit_enabled=False)
    parser.add_command(greet_with_address)
    cli = parser.build_parser()
    help_text = cli.format_help()

    assert "--user.name" in help_text
    assert "--user.age" in help_text
    assert "--user.address.city" in help_text
    assert "--user.address.zip" in help_text


def test_plain_class_model_expands_and_reconstructs() -> None:
    parser = Argparser(sys_exit_enabled=False)
    result = parser.run(greet_plain, args=["--user.name", "Ada", "--user.age", "32"])
    assert result == "Hello Ada, age 32"


def test_plain_class_docstring_help_used() -> None:
    parser = FakeParser(help_layout=InterfacyLayout())
    parser.register_command(Function(greet_plain), canonical_name="greet-plain")
    builder = ParserSchemaBuilder(parser)
    schema = builder.build()

    cmd = schema.commands["greet-plain"]
    help_text = {arg.name: arg.help or "" for arg in cmd.parameters}
    assert "Display name." in help_text["user.name"]
    assert "Age in years." in help_text["user.age"]


def test_plain_class_optional_none_when_no_flags() -> None:
    parser = Argparser(sys_exit_enabled=False)
    result = parser.run(maybe_plain, args=[])
    assert result is None


def test_plain_class_default_used_when_no_flags() -> None:
    parser = Argparser(sys_exit_enabled=False)
    result = parser.run(greet_plain_default, args=[])
    assert result == "Hello Tess, age 40"


def test_plain_class_default_merged_with_overrides() -> None:
    parser = Argparser(sys_exit_enabled=False)
    result = parser.run(greet_plain_default, args=["--user.age", "41"])
    assert result == "Hello Tess, age 41"


def test_plain_class_nested_expands_and_reconstructs() -> None:
    parser = Argparser(sys_exit_enabled=False)
    result = parser.run(
        greet_plain_with_address,
        args=[
            "--user.name",
            "Ada",
            "--user.age",
            "32",
            "--user.address.city",
            "Austin",
            "--user.address.zip",
            "78701",
        ],
    )
    assert result == "Hello Ada, age 32 from Austin 78701"


def test_pydantic_v2_model_expansion() -> None:
    pydantic = pytest.importorskip("pydantic")

    class PUser(pydantic.BaseModel):
        name: str = pydantic.Field(description="Display name.")
        age: int

    def greet_p(user: PUser) -> str:
        return user.name

    parser = FakeParser(help_layout=InterfacyLayout())
    parser.register_command(Function(greet_p), canonical_name="greet-p")
    builder = ParserSchemaBuilder(parser)
    schema = builder.build()

    cmd = schema.commands["greet-p"]
    names = {arg.name for arg in cmd.parameters}
    help_text = {arg.name: arg.help or "" for arg in cmd.parameters}

    assert "user.name" in names
    assert "user.age" in names
    assert "Display name." in help_text["user.name"]

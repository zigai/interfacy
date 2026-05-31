from dataclasses import dataclass, field
from typing import Any, Literal

import pytest
from objinspect import Function

from interfacy.appearance.layouts import InterfacyLayout
from interfacy.argparse_backend.argparser import Argparser
from interfacy.interfacy import Interfacy
from interfacy.schema.builder import ParserSchemaBuilder
from interfacy.schema.model_argument_mapper import ModelArgumentMapper
from interfacy.type_parsers import build_default_type_parser
from tests.schema.conftest import (
    Address,
    FakeParser,
    UserWithAddress,
    greet_plain,
    greet_plain_default,
    greet_plain_with_address,
    greet_with_address,
    maybe_plain,
    uses_levels,
)


@dataclass
class User:
    name: str
    age: int


def greet(user: User) -> str:
    return f"Hello {user.name}, age {user.age}"


@dataclass
class UserWithMetadataDescription:
    name: str = field(metadata={"description": "Display name from metadata."})


def greet_metadata(user: UserWithMetadataDescription) -> str:
    return f"Hello {user.name}"


@dataclass
class FutureInner:
    count: "int"
    mode: "Literal['fast', 'slow']" = "fast"


@dataclass
class FutureConfig:
    name: "str"
    inner: "FutureInner"
    tags: "list[int]" = field(default_factory=list)


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


def test_schema_expanded_fields_use_long_flags_by_default() -> None:
    parser = FakeParser()
    parser.register_command(Function(greet), canonical_name="greet")
    schema = ParserSchemaBuilder(parser).build()

    cmd = schema.commands["greet"]
    assert all(flags[0].startswith("--") for flags in (arg.flags for arg in cmd.parameters))


def test_schema_expanded_fields_can_generate_short_flags_for_all_options_scope() -> None:
    parser = FakeParser(abbreviation_scope="all_options")
    parser.register_command(Function(greet), canonical_name="greet")
    schema = ParserSchemaBuilder(parser).build()

    cmd = schema.commands["greet"]
    short_flags = [
        flag
        for arg in cmd.parameters
        for flag in arg.flags
        if flag.startswith("-") and not flag.startswith("--")
    ]
    assert short_flags


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


def test_partial_optional_nested_dataclass_reports_missing_required_flag(capsys) -> None:
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
        ],
    )

    assert isinstance(result, SystemExit)
    assert result.code == 2
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "--user.address.zip" in combined
    assert "required when --user.address.city is provided" in combined
    assert "TypeError" not in combined
    assert "Address.__init__" not in combined


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


def test_per_command_override_enables_model_expansion_when_parser_disabled() -> None:
    parser = Argparser(
        sys_exit_enabled=False,
        expand_model_params=False,
    )
    parser.add_command(greet_with_address, expand_model_params=True)

    schema = parser.build_parser_schema()
    command = schema.commands["greet-with-address"]
    names = {arg.name for arg in command.parameters}

    assert "user.name" in names
    assert command.expand_model_params is True

    result = parser.run(
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


def test_per_command_override_model_expansion_depth() -> None:
    parser = Argparser(
        sys_exit_enabled=False,
        model_expansion_max_depth=2,
    )
    parser.add_command(uses_levels, model_expansion_max_depth=4)

    schema = parser.build_parser_schema()
    command = schema.commands["uses-levels"]
    names = {arg.name for arg in command.parameters}

    assert "level1.level2.level3.leaf" in names
    assert command.model_expansion_max_depth == 4

    result = parser.run(args=["--level1.level2.level3.leaf", "x"])
    assert result == "x"


def test_per_command_override_abbreviation_scope() -> None:
    parser = Argparser(
        sys_exit_enabled=False,
        abbreviation_scope="top_level_options",
    )
    parser.add_command(greet_with_address, abbreviation_scope="all_options")
    schema = parser.build_parser_schema()
    command = schema.commands["greet-with-address"]

    name_arg = next(arg for arg in command.parameters if arg.name == "user.name")
    assert any(flag.startswith("-") and not flag.startswith("--") for flag in name_arg.flags)


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


def test_metadata_description_used_for_dataclass_fields() -> None:
    parser = FakeParser(help_layout=InterfacyLayout())
    parser.register_command(Function(greet_metadata), canonical_name="greet-metadata")
    builder = ParserSchemaBuilder(parser)
    schema = builder.build()

    cmd = schema.commands["greet-metadata"]
    help_text = {arg.name: arg.help or "" for arg in cmd.parameters}

    assert "Display name from metadata." in help_text["user.name"]


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


def test_dataclass_expansion_resolves_postponed_string_annotations() -> None:
    def command(config: FutureConfig) -> FutureConfig:
        return config

    for backend in ("argparse", "click"):
        parser = Interfacy(backend=backend, sys_exit_enabled=False)
        result = parser.run(
            command,
            args=[
                "--config.name",
                "n",
                "--config.inner.count",
                "3",
                "--config.tags",
                "1",
                "2",
            ],
        )

        assert result == FutureConfig(name="n", inner=FutureInner(count=3), tags=[1, 2])


def test_registered_parser_for_plain_class_prevents_model_expansion() -> None:
    class Custom:
        def __init__(self, value: str) -> None:
            self.value = value

    def parse_custom(raw: str) -> Custom:
        return Custom(raw.removeprefix("x:"))

    def command(value: Custom) -> Custom:
        return value

    type_parser = build_default_type_parser()
    type_parser.add(Custom, parse_custom)

    for backend in ("argparse", "click"):
        parser = Interfacy(backend=backend, sys_exit_enabled=False, type_parser=type_parser)
        result = parser.run(command, args=["x:ok"])

        assert isinstance(result, Custom)
        assert result.value == "ok"


class FakePydanticField:
    def __init__(
        self,
        annotation: Any,
        *,
        required: bool = False,
        default: Any = None,
        description: str | None = None,
        callable_required: bool = True,
    ) -> None:
        self.annotation = annotation
        self.required = required
        self.default = default
        self.description = description
        if callable_required:
            self.is_required = lambda: required
        else:
            self.is_required = required


class FakePydanticAddress:
    model_fields = {
        "city": FakePydanticField(str, required=True, description="City name."),
        "zip": FakePydanticField(int, required=True, description="Postal code."),
    }

    def __init__(self, **kwargs: Any) -> None:
        self.city = kwargs["city"]
        self.zip = kwargs["zip"]

    def model_dump(self) -> dict[str, Any]:
        return {"city": self.city, "zip": self.zip}


class FakePydanticUser:
    model_fields = {
        "name": FakePydanticField(str, required=True, description="Display name."),
        "age": FakePydanticField(int, default=7, description="Age in years."),
        "address": FakePydanticField(FakePydanticAddress, required=True),
    }

    def __init__(self, **kwargs: Any) -> None:
        self.name = kwargs["name"]
        self.age = kwargs.get("age", 7)
        self.address = kwargs["address"]

    def model_dump(self) -> dict[str, Any]:
        return {"name": self.name, "age": self.age, "address": self.address.model_dump()}


def greet_fake_pydantic(user: FakePydanticUser) -> str:
    return f"Hello {user.name}, age {user.age} from {user.address.city} {user.address.zip}"


def test_pydantic_like_v2_model_expands_without_optional_dependency() -> None:
    parser = FakeParser(help_layout=InterfacyLayout())
    parser.register_command(Function(greet_fake_pydantic), canonical_name="greet-fake")

    cmd = ParserSchemaBuilder(parser).build().commands["greet-fake"]
    help_text = {arg.name: arg.help or "" for arg in cmd.parameters}

    assert {arg.name for arg in cmd.parameters} == {
        "user.name",
        "user.age",
        "user.address.city",
        "user.address.zip",
    }
    assert "Display name." in help_text["user.name"]
    assert "City name." in help_text["user.address.city"]
    assert {arg.name: arg.required for arg in cmd.parameters}["user.age"] is False


def test_pydantic_like_v2_model_reconstructs_nested_values() -> None:
    parser = Argparser(sys_exit_enabled=False)

    result = parser.run(
        greet_fake_pydantic,
        args=[
            "--user.name",
            "Ada",
            "--user.address.city",
            "Austin",
            "--user.address.zip",
            "78701",
        ],
    )

    assert result == "Hello Ada, age 7 from Austin 78701"


def test_pydantic_like_v2_model_default_merges_nested_override() -> None:
    default_user = FakePydanticUser(
        name="Tess",
        age=40,
        address=FakePydanticAddress(city="Austin", zip=78701),
    )

    def command(user: FakePydanticUser = default_user) -> str:
        return f"{user.name}:{user.age}:{user.address.city}:{user.address.zip}"

    parser = Argparser(sys_exit_enabled=False)
    assert parser.run(command, args=["--user.address.zip", "78702"]) == "Tess:40:Austin:78702"


class FakeLegacyFieldInfo:
    def __init__(self, description: str | None = None) -> None:
        self.description = description


class FakeLegacyField:
    def __init__(
        self,
        outer_type_: Any,
        *,
        required: bool = False,
        default: Any = None,
        description: str | None = None,
    ) -> None:
        self.outer_type_ = outer_type_
        self.required = required
        self.default = default
        self.field_info = FakeLegacyFieldInfo(description)


class FakePydanticV1User:
    __fields__ = {
        "name": FakeLegacyField(str, required=True, description="Legacy display name."),
        "age": FakeLegacyField(int, default=9, description="Legacy age."),
    }

    def __init__(self, **kwargs: Any) -> None:
        self.name = kwargs["name"]
        self.age = kwargs.get("age", 9)

    def dict(self) -> dict[str, Any]:
        return {"name": self.name, "age": self.age}


def test_pydantic_like_v1_model_expands_field_metadata() -> None:
    def command(user: FakePydanticV1User) -> str:
        return user.name

    parser = FakeParser(help_layout=InterfacyLayout())
    parser.register_command(Function(command), canonical_name="legacy")

    cmd = ParserSchemaBuilder(parser).build().commands["legacy"]
    help_text = {arg.name: arg.help or "" for arg in cmd.parameters}

    assert {arg.name for arg in cmd.parameters} == {"user.name", "user.age"}
    assert "Legacy display name." in help_text["user.name"]
    assert {arg.name: arg.required for arg in cmd.parameters} == {
        "user.name": True,
        "user.age": False,
    }


def test_pydantic_like_v1_model_reconstructs_and_uses_default() -> None:
    def command(user: FakePydanticV1User) -> str:
        return f"{user.name}:{user.age}"

    parser = Argparser(sys_exit_enabled=False)

    assert parser.run(command, args=["--user.name", "Ada"]) == "Ada:9"


def test_model_mapper_optional_empty_nested_dict_becomes_none() -> None:
    mapper = ModelArgumentMapper()

    assert mapper._coerce_model_value(Address | None, {}) is None


def test_dataclass_expansion_falls_back_when_forward_reference_is_unresolved() -> None:
    @dataclass
    class BrokenReferenceConfig:
        value: Any

    BrokenReferenceConfig.__annotations__["value"] = "DoesNotExist"

    def command(config: BrokenReferenceConfig) -> BrokenReferenceConfig:
        return config

    parser = FakeParser(help_layout=InterfacyLayout())
    parser.register_command(Function(command), canonical_name="broken")
    cmd = ParserSchemaBuilder(parser).build().commands["broken"]

    arg = next(arg for arg in cmd.parameters if arg.name == "config.value")
    assert arg.type is Any

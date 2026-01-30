from dataclasses import dataclass
from typing import Any, Callable, Iterable, Sequence

import pytest
from objinspect import Class, Function, Method

from interfacy.appearance.layout import HelpLayout
from interfacy.naming import (
    AbbreviationGenerator,
    DefaultAbbreviationGenerator,
    DefaultFlagStrategy,
    FlagStrategy,
)
from interfacy.pipe import PipeTargets, build_pipe_targets_config
from interfacy.schema.schema import Command


class RecordingHelpLayout(HelpLayout):
    """HelpLayout double that records formatting calls for assertions."""

    def __init__(self) -> None:
        super().__init__()
        self.formatted_descriptions: list[str] = []
        self.class_help_calls: list[str] = []
        self.parameter_help_calls: list[str] = []

    def format_description(self, description: str) -> str:
        self.formatted_descriptions.append(description)
        return f"formatted::{description}"

    def get_help_for_parameter(
        self,
        param,
        flags: tuple[str, ...] | None = None,
    ) -> str:
        display = flags[0] if flags else param.name
        self.parameter_help_calls.append(display)
        return f"help::{display}"

    def get_help_for_class(self, command: Class) -> str:
        self.class_help_calls.append(command.name)
        return f"class::{command.name}"


class StubTypeParser:
    """Minimal StrToTypeParser substitute tracking requested parse functions."""

    def __init__(self) -> None:
        self.parsers: dict[type[Any] | None, Callable[[str], Any]] = {}
        self.requests: list[type[Any] | None] = []

    def register(self, typ: type[Any] | None, func: Callable[[str], Any]) -> None:
        self.parsers[typ] = func

    def get_parse_func(self, typ: type[Any] | None) -> Callable[[str], Any] | None:
        if typ is None:
            return None
        self.requests.append(typ)
        return self.parsers.get(typ)


def make_command_stub(
    obj: Class | Function | Method,
    *,
    layout: HelpLayout,
    canonical_name: str | None = None,
    aliases: Sequence[str] = (),
) -> Command:
    canonical = canonical_name or obj.name
    return Command(
        obj=obj,
        canonical_name=canonical,
        cli_name=canonical,
        aliases=tuple(aliases),
        raw_description=obj.description if hasattr(obj, "description") else None,
        help_layout=layout,
    )


@dataclass
class FakeParser:
    """Parser double exposing the minimum API ParserSchemaBuilder expects."""

    description: str | None = None
    epilog: str | None = None
    allow_args_from_file: bool = True
    flag_strategy: FlagStrategy | None = None
    abbreviation_gen: AbbreviationGenerator | None = None
    help_layout: HelpLayout | None = None
    type_parser: StubTypeParser | None = None
    pipe_targets: PipeTargets | None = None
    reserved_flags: Sequence[str] = ("help",)
    command_key: str | None = "command"
    metadata: dict[str, Any] | None = None
    expand_model_params: bool = True
    model_expansion_max_depth: int = 3

    def __post_init__(self) -> None:
        self.COMMAND_KEY = self.command_key
        self.RESERVED_FLAGS = list(self.reserved_flags)
        self.flag_strategy = self.flag_strategy or DefaultFlagStrategy(style="required_positional")
        self.abbreviation_gen = self.abbreviation_gen or DefaultAbbreviationGenerator()
        self.help_layout = self.help_layout or RecordingHelpLayout()
        self.help_layout.flag_generator = self.flag_strategy
        self.type_parser = self.type_parser or StubTypeParser()
        self.pipe_targets_default = self.pipe_targets
        self.commands: dict[str, Command] = {}
        self.method_skips: list[str] = ["__init__", "__repr__", "repr"]
        self.metadata = dict(self.metadata or {})
        self._pipe_targets: dict[tuple[str | None, str | None], PipeTargets] = {}

    def register_command(
        self,
        obj: Class | Function | Method,
        *,
        canonical_name: str | None = None,
        aliases: Sequence[str] = (),
        description: str | None = None,
    ) -> Command:
        canonical = canonical_name or obj.name
        command = Command(
            obj=obj,
            canonical_name=canonical,
            cli_name=canonical,
            aliases=tuple(aliases),
            raw_description=description,
            help_layout=self.help_layout,
        )
        self.commands[canonical] = command
        return command

    def set_pipe_target(
        self,
        canonical_name: str | None,
        pipe_targets: PipeTargets | Sequence[str] | str,
        subcommand: str | None = None,
    ) -> PipeTargets:
        config = (
            pipe_targets
            if isinstance(pipe_targets, PipeTargets)
            else build_pipe_targets_config(pipe_targets)
        )
        self._pipe_targets[(canonical_name, subcommand)] = config
        return config

    def resolve_pipe_targets_by_names(
        self,
        *,
        canonical_name: str | None,
        obj_name: str | None,
        aliases: Iterable[str] | None,
        subcommand: str | None,
        include_default: bool,
    ) -> PipeTargets | None:
        del obj_name, aliases
        key = (canonical_name, subcommand)
        if key in self._pipe_targets:
            return self._pipe_targets[key]
        if include_default:
            return self.pipe_targets_default
        return None


@dataclass
class Address:
    """Mailing address data for a user.

    Args:
        city: City name.
        zip: Postal or ZIP code.
    """

    city: str
    zip: int


@dataclass
class UserWithAddress:
    """User profile information for the CLI.

    Args:
        name: Display name.
        age: Age in years.
        address: Optional mailing address details.
    """

    name: str
    age: int
    address: Address | None = None


def greet_with_address(user: UserWithAddress) -> str:
    if user.address is None:
        return f"Hello {user.name}, age {user.age}"
    return f"Hello {user.name}, age {user.age} from {user.address.city} {user.address.zip}"


@dataclass
class Level3:
    leaf: str


@dataclass
class Level2:
    level3: Level3


@dataclass
class Level1:
    level2: Level2


def uses_levels(level1: Level1) -> str:
    return level1.level2.level3.leaf


class PlainUser:
    """Plain class user model.

    Args:
        name: Display name.
        age: Age in years.
    """

    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age


def greet_plain(user: PlainUser) -> str:
    return f"Hello {user.name}, age {user.age}"


def maybe_plain(user: PlainUser | None = None) -> PlainUser | None:
    return user


PLAIN_DEFAULT_USER = PlainUser(name="Tess", age=40)


def greet_plain_default(user: PlainUser = PLAIN_DEFAULT_USER) -> str:
    return f"Hello {user.name}, age {user.age}"


class PlainAddress:
    """Plain class address model.

    Args:
        city: City name.
        zip: Postal or ZIP code.
    """

    def __init__(self, city: str, zip: int) -> None:
        self.city = city
        self.zip = zip


class PlainUserWithAddress:
    """Plain class user model with address.

    Args:
        name: Display name.
        age: Age in years.
        address: Mailing address details.
    """

    def __init__(self, name: str, age: int, address: PlainAddress) -> None:
        self.name = name
        self.age = age
        self.address = address


def greet_plain_with_address(user: PlainUserWithAddress) -> str:
    return f"Hello {user.name}, age {user.age} from {user.address.city} {user.address.zip}"


@pytest.fixture
def builder_parser() -> FakeParser:
    """Return a fresh FakeParser for each test."""

    return FakeParser()

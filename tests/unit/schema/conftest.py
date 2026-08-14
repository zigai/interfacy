from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any

import pytest
from objinspect import Class, Function, Method

from interfacy.help.layout import HelpLayout
from interfacy.naming import (
    AbbreviationGenerator,
    DefaultAbbreviationGenerator,
    DefaultFlagStrategy,
    FlagStrategy,
)
from interfacy.pipe import PipeTargets, build_pipe_targets_config
from interfacy.schema.builder import SchemaBuildContext
from interfacy.schema.schema import Command
from interfacy.schema.sorting import (
    DEFAULT_HELP_OPTION_SORT_RULES,
    DEFAULT_HELP_SUBCOMMAND_SORT_RULES,
)


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
    canonical_name: str | None = None,
    aliases: Sequence[str] = (),
) -> Command:
    canonical = canonical_name or obj.name
    return Command(
        obj=obj,
        canonical_name=canonical,
        cli_name=canonical,
        aliases=tuple(aliases),
        raw_description=obj.description,
    )


@dataclass
class SchemaSource:
    """Mutable neutral source used to assemble SchemaBuildContext values."""

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
    include_inherited_methods: bool = False
    include_protected_methods: bool = False
    include_private_methods: bool = False
    include_staticmethods: bool = True
    include_classmethods: bool = False
    expand_model_params: bool = True
    model_expansion_max_depth: int = 3
    abbreviation_scope: str = "top_level_options"
    help_option_sort: list[str] | None = None
    help_subcommand_sort: list[str] | None = None
    abbreviation_max_generated_len: int = 1
    bool_negative_prefix: str = "no-"
    help_flags: tuple[str, ...] = ("--help",)

    def __post_init__(self) -> None:
        self.COMMAND_KEY = self.command_key
        self.RESERVED_FLAGS = [flag.lstrip("-") for flag in self.help_flags]
        self.flag_strategy = self.flag_strategy or DefaultFlagStrategy(style="required_positional")
        self.abbreviation_gen = self.abbreviation_gen or DefaultAbbreviationGenerator(
            max_generated_len=self.abbreviation_max_generated_len
        )
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

    def schema_context(self) -> SchemaBuildContext:
        return SchemaBuildContext(
            pipe_target_resolver=self.resolve_pipe_targets_by_names,
            description=self.description,
            epilog=self.epilog,
            commands=self.commands,
            command_key=self.COMMAND_KEY,
            reserved_flags=list(self.RESERVED_FLAGS),
            method_skips=list(self.method_skips),
            allow_args_from_file=self.allow_args_from_file,
            pipe_targets_default=self.pipe_targets_default,
            metadata=dict(self.metadata),
            executable_flags=[],
            type_parser=self.type_parser,
            flag_strategy=self.flag_strategy,
            abbreviation_gen=self.abbreviation_gen,
            include_inherited_methods=self.include_inherited_methods,
            include_protected_methods=self.include_protected_methods,
            include_private_methods=self.include_private_methods,
            include_staticmethods=self.include_staticmethods,
            include_classmethods=self.include_classmethods,
            expand_model_params=self.expand_model_params,
            model_expansion_max_depth=self.model_expansion_max_depth,
            abbreviation_scope=self.abbreviation_scope,
            help_option_sort=self.help_option_sort,
            help_subcommand_sort=self.help_subcommand_sort,
            help_option_sort_effective=list(DEFAULT_HELP_OPTION_SORT_RULES),
            help_subcommand_sort_effective=list(DEFAULT_HELP_SUBCOMMAND_SORT_RULES),
            bool_negative_prefix=self.bool_negative_prefix,
            help_flags=self.help_flags,
        )


@pytest.fixture
def schema_source() -> SchemaSource:
    """Return a fresh neutral schema source for each test."""
    return SchemaSource()

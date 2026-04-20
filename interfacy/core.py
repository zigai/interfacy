import sys
from abc import abstractmethod
from collections.abc import Callable, Iterable, Mapping, Sequence
from copy import deepcopy
from enum import IntEnum, auto
from typing import TYPE_CHECKING, Any, ClassVar, Final, Literal, TypedDict, TypeVar

from objinspect import Class, Function, Method, Parameter, inspect
from stdl.fs import read_piped
from strto import StrToTypeParser

from interfacy import console
from interfacy.appearance.help_sort import (
    DEFAULT_HELP_OPTION_SORT_RULES,
    DEFAULT_HELP_SUBCOMMAND_SORT_RULES,
    HelpOptionSortRule,
    HelpSubcommandSortRule,
    default_help_option_sort_rules,
    default_help_subcommand_sort_rules,
    resolve_help_option_sort_rules,
    resolve_help_subcommand_sort_rules,
)
from interfacy.appearance.layout import InterfacyColors
from interfacy.appearance.layouts import HelpLayout, StandardLayout
from interfacy.exceptions import (
    ConfigurationError,
    DuplicateCommandError,
    DuplicatePluginError,
    InvalidCommandError,
)
from interfacy.executable_flag import ExecutableFlag, normalize_executable_flags
from interfacy.logger import get_logger
from interfacy.naming import (
    AbbreviationGenerator,
    CommandNameRegistry,
    DefaultAbbreviationGenerator,
    DefaultFlagStrategy,
    FlagStrategy,
)
from interfacy.pipe import PipeTargets, build_pipe_targets_config
from interfacy.plugins import (
    AbortRecovery,
    ArgumentRef,
    InterfacyPlugin,
    ParseFailure,
    ParseFailureKind,
    ProvideArgumentValues,
)
from interfacy.schema.builder import ParserSchemaBuilder
from interfacy.type_parsers import build_default_type_parser
from interfacy.util import (
    resolve_objinspect_annotations,
    set_process_title_from_argv,
    validate_help_group,
)

if TYPE_CHECKING:
    from interfacy.group import CommandGroup
    from interfacy.schema.schema import Argument, Command, ParserSchema


COMMAND_KEY: Final[str] = "command"
PIPE_UNSET: Final[object] = object()
MAX_PARSE_RECOVERY_ATTEMPTS: Final[int] = 3
AbbreviationScope = Literal["top_level_options", "all_options"]
HelpOptionSort = list[HelpOptionSortRule] | None
HelpSubcommandSort = list[HelpSubcommandSortRule] | None
ABBREVIATION_SCOPE_VALUES: tuple[AbbreviationScope, ...] = (
    "top_level_options",
    "all_options",
)

F = TypeVar("F", bound=Callable[..., Any])
SortRuleT = TypeVar("SortRuleT")
ValidateInputT = TypeVar("ValidateInputT")
ValidateOutputT = TypeVar("ValidateOutputT")


class ResolvedCommandSettings(TypedDict):
    abbreviation_scope: AbbreviationScope | None
    executable_flags: list[ExecutableFlag] | None
    help_option_sort: HelpOptionSort
    help_subcommand_sort: HelpSubcommandSort
    model_expansion_max_depth: int | None
    help_group: str | None


logger = get_logger(__name__)


def validate_abbreviation_max_generated_len(value: int) -> int:
    if value < 1:
        raise ConfigurationError("abbreviation_max_generated_len must be >= 1")
    return value


def validate_abbreviation_scope(value: AbbreviationScope) -> AbbreviationScope:
    if value not in ABBREVIATION_SCOPE_VALUES:
        raise ConfigurationError(
            "abbreviation_scope must be one of: " + ", ".join(ABBREVIATION_SCOPE_VALUES)
        )
    return value


def validate_help_option_sort(value: object) -> HelpOptionSort:
    return resolve_help_option_sort_rules(value, value_name="help_option_sort")


def validate_help_subcommand_sort(value: object) -> HelpSubcommandSort:
    return resolve_help_subcommand_sort_rules(value, value_name="help_subcommand_sort")


def validate_model_expansion_max_depth(value: int) -> int:
    if value < 1:
        raise ConfigurationError("model_expansion_max_depth must be >= 1")
    return value


class ExitCode(IntEnum):
    """Exit code constants used by Interfacy."""

    SUCCESS = 0
    ERR_INVALID_ARGS = auto()
    ERR_PARSING = auto()
    ERR_RUNTIME = auto()
    ERR_RUNTIME_INTERNAL = auto()
    INTERRUPTED = 130  # Unix convention: 128 + SIGINT (2)


class InterfacyParser:
    """
    Base parser interface for building CLI commands from callables.

    Args:
        description (str | None): CLI description shown in help output.
        epilog (str | None): Epilog text shown after help output.
        help_layout (HelpLayout | None): Help layout implementation.
        type_parser (StrToTypeParser | None): Parser registry for typed arguments.
        help_colors (InterfacyColors | None): Override help color theme.
        run (bool): Whether to auto-run after command registration.
        print_result (bool): Whether to print returned results.
        tab_completion (bool): Whether to enable tab completion.
        full_error_traceback (bool): Whether to print full tracebacks.
        allow_args_from_file (bool): Allow @file argument expansion.
        sys_exit_enabled (bool): Whether to call sys.exit on completion.
        flag_strategy (FlagStrategy | None): Flag naming and style strategy.
        abbreviation_gen (AbbreviationGenerator | None): Abbreviation generator.
        abbreviation_max_generated_len (int): Max generated short-flag length.
        abbreviation_scope (AbbreviationScope): Which option groups receive generated short flags.
        help_option_sort (list[HelpOptionSortRule] | None): Rules for option row ordering in
            help output. When unset, layout defaults are used, then global defaults.
        help_subcommand_sort (list[HelpSubcommandSortRule] | None): Rules for command/subcommand
            row ordering in help output. When unset, layout defaults are used, then global
            defaults.
        help_position (int | None): Absolute column where help descriptions begin.
        executable_flags (Sequence[ExecutableFlag] | None): Parser-root executable flags.
        pipe_targets (PipeTargets | dict[str, Any] | Sequence[Any] | str | None): Pipe config.
        print_result_func (Callable): Function used to print results.
        include_inherited_methods (bool): Include inherited methods for class commands.
        include_classmethods (bool): Include classmethods as commands.
        on_interrupt (Callable[[KeyboardInterrupt], None] | None): Interrupt callback.
        silent_interrupt (bool): Suppress interrupt message output.
        reraise_interrupt (bool): Re-raise KeyboardInterrupt after handling.
        expand_model_params (bool): Expand model parameters into nested flags.
        model_expansion_max_depth (int): Max depth for model expansion.
    """

    RESERVED_FLAGS: ClassVar[list[str]] = []
    logger_message_tag: str = "interfacy"
    COMMAND_KEY: Final[str] = "command"

    def __init__(
        self,
        description: str | None = None,
        epilog: str | None = None,
        help_layout: HelpLayout | None = None,
        type_parser: StrToTypeParser | None = None,
        *,
        help_colors: InterfacyColors | None = None,
        run: bool = False,
        print_result: bool = False,
        tab_completion: bool = False,
        full_error_traceback: bool = False,
        allow_args_from_file: bool = True,
        sys_exit_enabled: bool = True,
        flag_strategy: FlagStrategy | None = None,
        abbreviation_gen: AbbreviationGenerator | None = None,
        abbreviation_max_generated_len: int = 1,
        abbreviation_scope: AbbreviationScope = "top_level_options",
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_position: int | None = None,
        executable_flags: Sequence[ExecutableFlag] | None = None,
        pipe_targets: PipeTargets | dict[str, Any] | Sequence[Any] | str | None = None,
        print_result_func: Callable[[Any], Any] = print,
        include_inherited_methods: bool = False,
        include_classmethods: bool = False,
        on_interrupt: Callable[[KeyboardInterrupt], None] | None = None,
        silent_interrupt: bool = True,
        reraise_interrupt: bool = False,
        expand_model_params: bool = True,
        model_expansion_max_depth: int = 3,
        plugins: Sequence[InterfacyPlugin] | None = None,
    ) -> None:
        self.description = description
        self.epilog = epilog
        self.method_skips: list[str] = ["__init__", "__repr__", "repr"]
        self.pipe_targets_default: PipeTargets | None = (
            build_pipe_targets_config(pipe_targets) if pipe_targets is not None else None
        )
        self._pipe_target_overrides: dict[tuple[str | None, str | None], PipeTargets] = {}
        self._pipe_buffer: str | None | object = PIPE_UNSET
        self.result_display_fn = print_result_func
        self.metadata: dict[str, Any] = {}
        self.include_inherited_methods = include_inherited_methods
        self.include_classmethods = include_classmethods
        self.expand_model_params = expand_model_params
        self.model_expansion_max_depth = validate_model_expansion_max_depth(
            model_expansion_max_depth
        )
        self.abbreviation_max_generated_len = validate_abbreviation_max_generated_len(
            abbreviation_max_generated_len
        )
        self.abbreviation_scope = validate_abbreviation_scope(abbreviation_scope)
        self.help_option_sort = validate_help_option_sort(help_option_sort)
        self.help_option_sort_effective = default_help_option_sort_rules()
        self.help_subcommand_sort = validate_help_subcommand_sort(help_subcommand_sort)
        self.help_subcommand_sort_effective = default_help_subcommand_sort_rules()
        self.executable_flags = normalize_executable_flags(
            executable_flags,
            value_name="executable_flags",
        )
        self.help_position = help_position
        self._help_layout_explicit = help_layout is not None
        self._help_position_explicit = help_position is not None or (
            help_layout is not None and help_layout.help_position is not None
        )

        self.autorun = run
        self.allow_args_from_file = allow_args_from_file
        self.full_error_traceback = full_error_traceback
        self.enable_tab_completion = tab_completion
        self.sys_exit_enabled = sys_exit_enabled
        self.display_result = print_result
        self.on_interrupt = on_interrupt
        self.silent_interrupt = silent_interrupt
        self.reraise_interrupt = reraise_interrupt

        self.abbreviation_gen = abbreviation_gen or DefaultAbbreviationGenerator(
            max_generated_len=self.abbreviation_max_generated_len
        )
        self._type_parser_explicit = type_parser is not None
        self.type_parser = (
            type_parser
            if type_parser is not None
            else build_default_type_parser(from_file=allow_args_from_file)
        )
        self.flag_strategy = flag_strategy or DefaultFlagStrategy()
        self.help_layout = deepcopy(help_layout) if help_layout is not None else StandardLayout()
        if help_position is not None:
            self.help_layout.help_position = help_position
        if help_colors is not None:
            self.help_layout.style = help_colors
        self._refresh_help_option_sort_rules()
        self._refresh_help_subcommand_sort_rules()
        self.help_colors = self.help_layout.style
        self.help_layout.flag_generator = self.flag_strategy
        self.name_registry = CommandNameRegistry(self.flag_strategy.command_translator)
        self.help_layout.name_registry = self.name_registry

        self.commands: dict[str, Command] = {}
        self.plugins: list[InterfacyPlugin] = []
        self._plugin_names: set[str] = set()
        if plugins:
            for plugin in plugins:
                self.add_plugin(plugin)

    def _snapshot_backend_registration_state(self) -> object | None:
        """Capture backend-specific mutable registration state."""
        return None

    def _restore_backend_registration_state(self, snapshot: object | None) -> None:
        """Restore backend-specific mutable registration state."""

    def _invalidate_backend_build_cache(self) -> None:
        """Clear backend-specific cached parser state after runtime config changes."""

    def _invalidate_build_cache(self) -> None:
        """Clear any cached parser/schema state after configuration changes."""
        self._invalidate_backend_build_cache()

    def add_plugin(self, plugin: InterfacyPlugin) -> InterfacyPlugin:
        """Register a plugin on this parser and run its configure hook immediately."""
        plugin_name = plugin.plugin_name
        if plugin_name in self._plugin_names:
            raise DuplicatePluginError(plugin_name)

        self._plugin_names.add(plugin_name)
        try:
            plugin.configure(self)
        except Exception:
            self._plugin_names.remove(plugin_name)
            raise
        self.plugins.append(plugin)
        self._invalidate_build_cache()
        return plugin

    def _validate_apply_setup_request(
        self,
        *,
        flag_strategy: FlagStrategy | None,
    ) -> None:
        if flag_strategy is not None and self.commands:
            raise ConfigurationError(
                "flag_strategy cannot be changed after commands have been registered"
            )

    def _apply_layout_setup(
        self,
        *,
        help_layout: HelpLayout | None,
        help_colors: InterfacyColors | None,
        help_position: int | None,
    ) -> None:
        if help_layout is not None:
            self.help_layout = deepcopy(help_layout)
            self._help_layout_explicit = True

        if help_position is not None:
            self.help_position = help_position
            self.help_layout.help_position = help_position
            self._help_position_explicit = True

        if help_colors is not None:
            self.help_layout.style = help_colors

    def _apply_type_parser_setup(
        self,
        *,
        type_parser: StrToTypeParser | None,
        allow_args_from_file: bool | None,
    ) -> None:
        if type_parser is not None:
            self.type_parser = type_parser
            self._type_parser_explicit = True
            return

        if allow_args_from_file is not None and not self._type_parser_explicit:
            self.type_parser = build_default_type_parser(from_file=allow_args_from_file)

    def _apply_runtime_setup(
        self,
        *,
        print_result: bool | None,
        tab_completion: bool | None,
        full_error_traceback: bool | None,
        allow_args_from_file: bool | None,
        include_inherited_methods: bool | None,
        include_classmethods: bool | None,
        silent_interrupt: bool | None,
        expand_model_params: bool | None,
        model_expansion_max_depth: int | None,
    ) -> None:
        optional_updates = (
            ("display_result", print_result),
            ("enable_tab_completion", tab_completion),
            ("full_error_traceback", full_error_traceback),
            ("allow_args_from_file", allow_args_from_file),
            ("include_inherited_methods", include_inherited_methods),
            ("include_classmethods", include_classmethods),
            ("silent_interrupt", silent_interrupt),
            ("expand_model_params", expand_model_params),
        )
        self._apply_optional_attr_updates(optional_updates)

        if model_expansion_max_depth is not None:
            self.model_expansion_max_depth = validate_model_expansion_max_depth(
                model_expansion_max_depth
            )

    def _apply_optional_attr_updates(
        self,
        updates: Sequence[tuple[str, object | None]],
    ) -> None:
        for attr_name, value in updates:
            if value is not None:
                setattr(self, attr_name, value)

    def _apply_help_and_abbreviation_setup(
        self,
        *,
        abbreviation_max_generated_len: int | None,
        abbreviation_scope: AbbreviationScope | None,
        help_option_sort: list[HelpOptionSortRule] | None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None,
    ) -> None:
        if abbreviation_max_generated_len is not None:
            self.abbreviation_max_generated_len = validate_abbreviation_max_generated_len(
                abbreviation_max_generated_len
            )
        if abbreviation_scope is not None:
            self.abbreviation_scope = validate_abbreviation_scope(abbreviation_scope)
        if help_option_sort is not None:
            self.help_option_sort = validate_help_option_sort(help_option_sort)
        if help_subcommand_sort is not None:
            self.help_subcommand_sort = validate_help_subcommand_sort(help_subcommand_sort)

    def _apply_naming_setup(
        self,
        *,
        flag_strategy: FlagStrategy | None,
        abbreviation_gen: AbbreviationGenerator | None,
        abbreviation_max_generated_len: int | None,
    ) -> None:
        if flag_strategy is not None:
            self.flag_strategy = flag_strategy
            self.name_registry = CommandNameRegistry(self.flag_strategy.command_translator)

        if abbreviation_gen is not None:
            self.abbreviation_gen = abbreviation_gen
        elif abbreviation_max_generated_len is not None:
            self.abbreviation_gen = DefaultAbbreviationGenerator(
                max_generated_len=self.abbreviation_max_generated_len
            )

    def _finalize_setup_changes(self) -> None:
        self.help_layout.flag_generator = self.flag_strategy
        self.help_layout.name_registry = self.name_registry
        self._refresh_help_option_sort_rules()
        self._refresh_help_subcommand_sort_rules()
        self.help_colors = self.help_layout.style
        self._invalidate_build_cache()

    def apply_setup(
        self,
        *,
        help_layout: HelpLayout | None = None,
        help_colors: InterfacyColors | None = None,
        type_parser: StrToTypeParser | None = None,
        print_result: bool | None = None,
        tab_completion: bool | None = None,
        full_error_traceback: bool | None = None,
        allow_args_from_file: bool | None = None,
        flag_strategy: FlagStrategy | None = None,
        abbreviation_gen: AbbreviationGenerator | None = None,
        abbreviation_max_generated_len: int | None = None,
        abbreviation_scope: AbbreviationScope | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_position: int | None = None,
        include_inherited_methods: bool | None = None,
        include_classmethods: bool | None = None,
        silent_interrupt: bool | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        plugins: Sequence[InterfacyPlugin] | None = None,
    ) -> None:
        """Apply parser-level setup after construction."""
        self._validate_apply_setup_request(flag_strategy=flag_strategy)
        self._apply_layout_setup(
            help_layout=help_layout,
            help_colors=help_colors,
            help_position=help_position,
        )
        self._apply_type_parser_setup(
            type_parser=type_parser,
            allow_args_from_file=allow_args_from_file,
        )
        self._apply_runtime_setup(
            print_result=print_result,
            tab_completion=tab_completion,
            full_error_traceback=full_error_traceback,
            allow_args_from_file=allow_args_from_file,
            include_inherited_methods=include_inherited_methods,
            include_classmethods=include_classmethods,
            silent_interrupt=silent_interrupt,
            expand_model_params=expand_model_params,
            model_expansion_max_depth=model_expansion_max_depth,
        )
        self._apply_help_and_abbreviation_setup(
            abbreviation_max_generated_len=abbreviation_max_generated_len,
            abbreviation_scope=abbreviation_scope,
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
        )
        self._apply_naming_setup(
            flag_strategy=flag_strategy,
            abbreviation_gen=abbreviation_gen,
            abbreviation_max_generated_len=abbreviation_max_generated_len,
        )
        self._finalize_setup_changes()

        if plugins:
            for plugin in plugins:
                self.add_plugin(plugin)

    def _transform_schema_with_plugins(self, schema: "ParserSchema") -> "ParserSchema":
        for plugin in self.plugins:
            schema = plugin.transform_schema(self, schema)
        return schema

    def _recover_parse_failure(
        self,
        failure: ParseFailure,
    ) -> AbortRecovery | ProvideArgumentValues | None:
        for plugin in self.plugins:
            action = plugin.recover_parse_failure(self, failure)
            if action is not None:
                return action
        return None

    def _single_command_without_root_selection(self, schema: "ParserSchema") -> "Command | None":
        if len(schema.commands) != 1:
            return None
        command = next(iter(schema.commands.values()))
        if command.command_type == "group":
            return None
        return command

    def _match_command_name(
        self,
        commands: Mapping[str, "Command"],
        cli_name: str,
    ) -> "Command | None":
        for command in commands.values():
            if command.cli_name == cli_name or cli_name in command.aliases:
                return command
        return None

    def _bucket_for_command_path(
        self,
        schema: "ParserSchema",
        namespace: dict[str, Any],
        command_path: tuple[str, ...],
        *,
        create: bool = False,
    ) -> dict[str, Any] | None:
        root_command = self._single_command_without_root_selection(schema)
        if root_command is not None and not command_path:
            return namespace

        if not command_path:
            return namespace

        current: dict[str, Any] = namespace
        for segment in command_path:
            value = current.get(segment)
            if not isinstance(value, dict):
                if not create:
                    return None
                value = {}
                current[segment] = value
            current = value
        return current

    def _build_missing_arguments_failure(
        self,
        *,
        backend: str,
        message: str,
        command_path: tuple[str, ...],
        command_depth: int,
        arguments: Sequence["Argument"],
        missing_names: Sequence[str],
        raw_exception: BaseException | None,
    ) -> ParseFailure | None:
        refs: list[ArgumentRef] = []
        remaining = list(missing_names)
        for argument in arguments:
            if not argument.required:
                continue
            if self._argument_matches_missing_tokens(argument, remaining):
                refs.append(
                    ArgumentRef(command_path=command_path, name=argument.name, argument=argument)
                )

        if not refs:
            return None

        return ParseFailure(
            backend=backend,
            kind=ParseFailureKind.MISSING_ARGUMENTS,
            message=message,
            command_path=command_path,
            command_depth=command_depth,
            missing_arguments=tuple(refs),
            raw_exception=raw_exception,
        )

    @staticmethod
    def _normalize_missing_token(token: str) -> str:
        return token.strip().lstrip("-").replace("-", "_").replace(".", "_").upper()

    def _argument_matches_missing_tokens(
        self,
        argument: "Argument",
        missing_names: list[str],
    ) -> bool:
        possible_tokens = {self._normalize_missing_token(argument.name)}
        possible_tokens.add(self._normalize_missing_token(argument.display_name))
        if argument.metavar:
            possible_tokens.add(self._normalize_missing_token(argument.metavar))
        for flag in argument.flags:
            possible_tokens.add(self._normalize_missing_token(flag))

        for raw_name in list(missing_names):
            split_names = [part for part in raw_name.split("/") if part]
            normalized = {self._normalize_missing_token(name) for name in split_names}
            if normalized & possible_tokens:
                missing_names.remove(raw_name)
                return True
        return False

    def _find_first_missing_from_namespace(
        self,
        schema: "ParserSchema",
        namespace: dict[str, Any],
        *,
        backend: str,
        message: str,
        raw_exception: BaseException | None,
    ) -> ParseFailure | None:
        root_command = self._single_command_without_root_selection(schema)
        if root_command is not None:
            return self._find_missing_for_command(
                root_command,
                namespace,
                bucket_path=(),
                depth=0,
                backend=backend,
                message=message,
                raw_exception=raw_exception,
            )

        command_name = namespace.get(self.COMMAND_KEY)
        if not isinstance(command_name, str):
            return ParseFailure(
                backend=backend,
                kind=ParseFailureKind.MISSING_SUBCOMMAND,
                message=message,
                command_path=(),
                command_depth=0,
                available_subcommands=tuple(schema.commands.keys()),
                raw_exception=raw_exception,
            )

        command = self._match_command_name(schema.commands, command_name)
        if command is None:
            return None

        bucket = (
            self._bucket_for_command_path(
                schema, namespace, (command.canonical_name,), create=False
            )
            or {}
        )
        return self._find_missing_for_command(
            command,
            bucket,
            bucket_path=(command.canonical_name,),
            depth=0,
            backend=backend,
            message=message,
            raw_exception=raw_exception,
        )

    def _find_missing_for_command(
        self,
        command: "Command",
        bucket: dict[str, Any],
        *,
        bucket_path: tuple[str, ...],
        depth: int,
        backend: str,
        message: str,
        raw_exception: BaseException | None,
    ) -> ParseFailure | None:
        missing_args = [
            arg
            for arg in [*command.initializer, *command.parameters]
            if self._argument_value_is_missing(arg, bucket)
        ]
        if missing_args:
            return ParseFailure(
                backend=backend,
                kind=ParseFailureKind.MISSING_ARGUMENTS,
                message=message,
                command_path=bucket_path,
                command_depth=depth,
                missing_arguments=tuple(
                    ArgumentRef(command_path=bucket_path, name=argument.name, argument=argument)
                    for argument in missing_args
                ),
                raw_exception=raw_exception,
            )

        if not command.subcommands:
            return None

        dest_key = self.COMMAND_KEY if depth == 0 else f"{self.COMMAND_KEY}_{depth}"
        selected = bucket.get(dest_key)
        if not isinstance(selected, str):
            return ParseFailure(
                backend=backend,
                kind=ParseFailureKind.MISSING_SUBCOMMAND,
                message=message,
                command_path=bucket_path,
                command_depth=depth,
                available_subcommands=tuple(command.subcommands.keys()),
                raw_exception=raw_exception,
            )

        subcommand = self._match_command_name(command.subcommands, selected)
        if subcommand is None:
            return None

        next_bucket_path = (*bucket_path, subcommand.cli_name)
        next_bucket = bucket.get(subcommand.cli_name)
        if not isinstance(next_bucket, dict):
            next_bucket = {}
        return self._find_missing_for_command(
            subcommand,
            next_bucket,
            bucket_path=next_bucket_path,
            depth=depth + 1,
            backend=backend,
            message=message,
            raw_exception=raw_exception,
        )

    @staticmethod
    def _argument_value_is_missing(
        argument: "Argument",
        bucket: Mapping[str, Any],
    ) -> bool:
        if not argument.required:
            return False

        if argument.name not in bucket:
            return True

        value = bucket[argument.name]
        if value is None:
            return True

        if (
            argument.value_shape.name == "LIST"
            and isinstance(value, Sequence)
            and not isinstance(value, (str, bytes, bytearray))
        ):
            return len(value) == 0

        if (
            argument.value_shape.name == "TUPLE"
            and isinstance(argument.nargs, int)
            and isinstance(value, Sequence)
            and not isinstance(value, (str, bytes, bytearray))
        ):
            return len(value) < argument.nargs

        return False

    def _apply_recovery_action(
        self,
        schema: "ParserSchema",
        namespace: dict[str, Any],
        action: ProvideArgumentValues,
    ) -> None:
        for command_path, subcommand_name in action.subcommands.items():
            if command_path:
                bucket = self._bucket_for_command_path(schema, namespace, command_path, create=True)
                assert bucket is not None
                depth = max(len(command_path) - 1, 0)
                root_command = self._single_command_without_root_selection(schema)
                if root_command is not None and not command_path:
                    depth = 0
                if root_command is not None and command_path:
                    depth = len(command_path)
                dest_key = self.COMMAND_KEY if depth == 0 else f"{self.COMMAND_KEY}_{depth}"
                bucket[dest_key] = subcommand_name
                bucket.setdefault(subcommand_name, {})
                continue

            namespace[self.COMMAND_KEY] = subcommand_name
            namespace.setdefault(subcommand_name, {})

        for argument_ref, value in action.values.items():
            bucket = self._bucket_for_command_path(
                schema, namespace, argument_ref.command_path, create=True
            )
            if bucket is None:
                raise ConfigurationError(
                    f"Could not resolve recovery command path: {argument_ref.command_path!r}"
                )
            bucket[argument_ref.name] = value

    def _recover_namespace_from_partial_parse(
        self,
        schema: "ParserSchema",
        namespace: dict[str, Any],
        *,
        backend: str,
        message: str,
        raw_exception: BaseException | None,
    ) -> dict[str, Any] | None:
        attempts = 0
        failure = self._find_first_missing_from_namespace(
            schema,
            namespace,
            backend=backend,
            message=message,
            raw_exception=raw_exception,
        )
        while failure is not None and attempts < MAX_PARSE_RECOVERY_ATTEMPTS:
            action = self._recover_parse_failure(failure)
            if action is None:
                return None
            if isinstance(action, AbortRecovery):
                if action.message:
                    console.error(action.message)
                raise SystemExit(action.exit_code)

            self._apply_recovery_action(schema, namespace, action)
            attempts += 1
            failure = self._find_first_missing_from_namespace(
                schema,
                namespace,
                backend=backend,
                message=message,
                raw_exception=raw_exception,
            )

        if failure is not None:
            return None
        return namespace

    def _snapshot_registration_state(self) -> dict[str, object]:
        """Capture mutable registration state so inline run() registrations can be temporary."""
        return {
            "commands": dict(self.commands),
            "pipe_target_overrides": dict(self._pipe_target_overrides),
            "pipe_buffer": self._pipe_buffer,
            "name_registry": self.name_registry.snapshot(),
            "backend": self._snapshot_backend_registration_state(),
            "plugins": list(self.plugins),
            "plugin_names": set(self._plugin_names),
        }

    def _restore_registration_state(self, snapshot: dict[str, object]) -> None:
        """Restore a previously captured registration snapshot."""
        self.commands = dict(snapshot["commands"])
        self._pipe_target_overrides = dict(snapshot["pipe_target_overrides"])
        self._pipe_buffer = snapshot["pipe_buffer"]
        self.name_registry.restore(snapshot["name_registry"])
        self.plugins = list(snapshot["plugins"])
        self._plugin_names = set(snapshot["plugin_names"])
        self._restore_backend_registration_state(snapshot.get("backend"))

    def _resolve_help_option_sort_from_layout(
        self,
        help_layout: HelpLayout,
    ) -> list[HelpOptionSortRule]:
        return self._resolve_help_sort_from_layout(
            help_layout=help_layout,
            user_value=self.help_option_sort,
            user_validator=validate_help_option_sort,
            layout_default_value=help_layout.help_option_sort_default,
            layout_default_name="help_option_sort_default",
            layout_resolver=resolve_help_option_sort_rules,
            default_rules=DEFAULT_HELP_OPTION_SORT_RULES,
        )

    def _resolve_help_sort_from_layout(
        self,
        *,
        help_layout: HelpLayout,
        user_value: object,
        user_validator: Callable[[object], list[SortRuleT] | None],
        layout_default_value: object,
        layout_default_name: str,
        layout_resolver: Callable[..., list[SortRuleT] | None],
        default_rules: Sequence[SortRuleT],
    ) -> list[SortRuleT]:
        user_rules = user_validator(user_value)
        if user_rules:
            return list(user_rules)

        layout_rules = layout_resolver(
            layout_default_value,
            value_name=f"{help_layout.__class__.__name__}.{layout_default_name}",
        )
        if layout_rules:
            return list(layout_rules)

        return list(default_rules)

    def _refresh_help_option_sort_rules(self) -> list[HelpOptionSortRule]:
        """Resolve and apply effective help option sort rules to the active layout."""
        return self._refresh_help_sort_rules(
            effective_attr="help_option_sort_effective",
            layout_rules_attr="help_option_sort_rules",
            default_rules=DEFAULT_HELP_OPTION_SORT_RULES,
            resolve_rules=self._resolve_help_option_sort_from_layout,
        )

    def _resolve_help_subcommand_sort_from_layout(
        self,
        help_layout: HelpLayout,
    ) -> list[HelpSubcommandSortRule]:
        return self._resolve_help_sort_from_layout(
            help_layout=help_layout,
            user_value=self.help_subcommand_sort,
            user_validator=validate_help_subcommand_sort,
            layout_default_value=help_layout.help_subcommand_sort_default,
            layout_default_name="help_subcommand_sort_default",
            layout_resolver=resolve_help_subcommand_sort_rules,
            default_rules=DEFAULT_HELP_SUBCOMMAND_SORT_RULES,
        )

    def _refresh_help_subcommand_sort_rules(self) -> list[HelpSubcommandSortRule]:
        """Resolve and apply effective help subcommand sort rules to the active layout."""
        return self._refresh_help_sort_rules(
            effective_attr="help_subcommand_sort_effective",
            layout_rules_attr="help_subcommand_sort_rules",
            default_rules=DEFAULT_HELP_SUBCOMMAND_SORT_RULES,
            resolve_rules=self._resolve_help_subcommand_sort_from_layout,
        )

    def _refresh_help_sort_rules(
        self,
        *,
        effective_attr: str,
        layout_rules_attr: str,
        default_rules: Sequence[SortRuleT],
        resolve_rules: Callable[[HelpLayout], list[SortRuleT]],
    ) -> list[SortRuleT]:
        if self.help_layout is None:
            effective_rules = list(default_rules)
            setattr(self, effective_attr, list(effective_rules))
            return list(effective_rules)

        effective_rules = list(resolve_rules(self.help_layout))
        setattr(self, effective_attr, list(effective_rules))
        setattr(self.help_layout, layout_rules_attr, list(effective_rules))
        return list(effective_rules)

    def refresh_help_option_sort_rules(self) -> list[HelpOptionSortRule]:
        """
        Public hook to recompute help option sort rules after runtime settings changes.

        Returns:
            list[HelpOptionSortRule]: Effective rules applied to the current layout.
        """
        return self._refresh_help_option_sort_rules()

    def refresh_help_subcommand_sort_rules(self) -> list[HelpSubcommandSortRule]:
        """
        Public hook to recompute help subcommand sort rules after runtime settings changes.

        Returns:
            list[HelpSubcommandSortRule]: Effective rules applied to the current layout.
        """
        return self._refresh_help_subcommand_sort_rules()

    @staticmethod
    def _validate_optional(
        value: ValidateInputT | None,
        validator: Callable[[ValidateInputT], ValidateOutputT],
    ) -> ValidateOutputT | None:
        if value is None:
            return None
        return validator(value)

    @staticmethod
    def _copy_optional_list(value: list[SortRuleT] | None) -> list[SortRuleT] | None:
        if value is None:
            return None
        return list(value)

    def _resolve_command_settings(
        self,
        *,
        abbreviation_scope: AbbreviationScope | None,
        executable_flags: list[ExecutableFlag] | None,
        help_option_sort: list[HelpOptionSortRule] | None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None,
        model_expansion_max_depth: int | None,
        help_group: str | None,
    ) -> ResolvedCommandSettings:
        return {
            "abbreviation_scope": self._validate_optional(
                abbreviation_scope,
                validate_abbreviation_scope,
            ),
            "executable_flags": self._copy_optional_list(
                normalize_executable_flags(
                    executable_flags,
                    value_name="executable_flags",
                )
            ),
            "help_option_sort": self._validate_optional(
                help_option_sort,
                validate_help_option_sort,
            ),
            "help_subcommand_sort": self._validate_optional(
                help_subcommand_sort,
                validate_help_subcommand_sort,
            ),
            "model_expansion_max_depth": self._validate_optional(
                model_expansion_max_depth,
                validate_model_expansion_max_depth,
            ),
            "help_group": validate_help_group(help_group),
        }

    @staticmethod
    def _apply_command_settings(
        command: "Command",
        *,
        include_inherited_methods: bool | None,
        include_classmethods: bool | None,
        expand_model_params: bool | None,
        model_expansion_max_depth: int | None,
        abbreviation_scope: AbbreviationScope | None,
        executable_flags: list[ExecutableFlag] | None,
        help_option_sort: HelpOptionSort,
        help_subcommand_sort: HelpSubcommandSort,
        help_group: str | None,
    ) -> None:
        command.include_inherited_methods = include_inherited_methods
        command.include_classmethods = include_classmethods
        command.expand_model_params = expand_model_params
        command.model_expansion_max_depth = model_expansion_max_depth
        command.abbreviation_scope = abbreviation_scope
        command.executable_flags = InterfacyParser._copy_optional_list(executable_flags) or []
        command.help_option_sort = InterfacyParser._copy_optional_list(help_option_sort)
        command.help_subcommand_sort = InterfacyParser._copy_optional_list(help_subcommand_sort)
        command.help_group = help_group

    def add_command(
        self,
        command: object,
        name: str | None = None,
        description: str | None = None,
        aliases: Sequence[str] | None = None,
        pipe_targets: PipeTargets | dict[str, Any] | Sequence[str] | str | None = None,
        include_inherited_methods: bool | None = None,
        include_classmethods: bool | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: AbbreviationScope | None = None,
        executable_flags: list[ExecutableFlag] | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
    ) -> "Command":
        """
        Register a command callable or group with the parser.

        Args:
            command (Callable | Any): Function, class, instance, or CommandGroup.
            name (str | None): Optional CLI name override.
            description (str | None): Optional description override.
            aliases (Sequence[str] | None): Alternative CLI names.
            pipe_targets (PipeTargets | dict[str, Any] | Sequence[str] | str | None): Pipe config.
            include_inherited_methods (bool | None): Override inherited-method inclusion.
            include_classmethods (bool | None): Override classmethod inclusion.
            expand_model_params (bool | None): Override model expansion toggle.
            model_expansion_max_depth (int | None): Override model expansion depth.
            abbreviation_scope (AbbreviationScope | None): Override abbreviation scope.
            executable_flags (list[ExecutableFlag] | None): Zero-argument executable flags.
            help_option_sort (list[HelpOptionSortRule] | None): Override option sort rules.
            help_subcommand_sort (list[HelpSubcommandSortRule] | None): Override subcommand sort.
            help_group (str | None): Optional help-only command group heading.

        Raises:
            DuplicateCommandError: If the command name is already registered.
        """
        from interfacy.group import CommandGroup

        resolved_settings = self._resolve_command_settings(
            abbreviation_scope=abbreviation_scope,
            executable_flags=executable_flags,
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
            model_expansion_max_depth=model_expansion_max_depth,
            help_group=help_group,
        )

        if isinstance(command, CommandGroup):
            return self.add_group(
                command,
                name=name,
                description=description,
                aliases=aliases,
                include_inherited_methods=include_inherited_methods,
                include_classmethods=include_classmethods,
                expand_model_params=expand_model_params,
                **resolved_settings,
            )

        obj = inspect(
            command,
            init=True,
            public=True,
            inherited=(
                include_inherited_methods
                if include_inherited_methods is not None
                else self.include_inherited_methods
            ),
            static_methods=True,
            classmethod=(
                include_classmethods
                if include_classmethods is not None
                else self.include_classmethods
            ),
            protected=False,
            private=False,
        )
        resolve_objinspect_annotations(obj)

        canonical_name, command_aliases = self.name_registry.register(
            default_name=obj.name,
            explicit_name=name,
            aliases=aliases,
        )

        if canonical_name in self.commands:
            raise DuplicateCommandError(canonical_name)

        if pipe_targets is not None:
            config = build_pipe_targets_config(pipe_targets)
            self._pipe_target_overrides[(canonical_name, None)] = config

        raw_description = (
            description
            if description is not None
            else (obj.description if obj.has_docstring else None)
        )
        from interfacy.schema.schema import Command

        command = Command(
            obj=obj,
            canonical_name=canonical_name,
            cli_name=canonical_name,
            aliases=tuple(command_aliases),
            raw_description=raw_description,
            parameters=[],
            initializer=[],
            subcommands=None,
            pipe_targets=None,
            help_layout=self.help_layout,
        )
        self._apply_command_settings(
            command,
            include_inherited_methods=include_inherited_methods,
            include_classmethods=include_classmethods,
            expand_model_params=expand_model_params,
            **resolved_settings,
        )
        self.commands[canonical_name] = command
        logger.debug("Added command: %s", command)
        return command

    def command(
        self,
        name: str | None = None,
        description: str | None = None,
        aliases: Sequence[str] | None = None,
        pipe_targets: PipeTargets | dict[str, Any] | Sequence[str] | str | None = None,
        include_inherited_methods: bool | None = None,
        include_classmethods: bool | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: AbbreviationScope | None = None,
        executable_flags: list[ExecutableFlag] | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
    ) -> Callable[[F], F]:
        """
        Decorator to register a command with the parser.

        This is syntactic sugar for `add_command()` that allows decorator-style
        command registration. The decorated function/class remains unchanged.

        Args:
            name: Override the command name (defaults to function/class name).
            description: Override the description (defaults to docstring).
            aliases: Alternative names for this command.
            pipe_targets: Configure stdin piping for this command.
            include_inherited_methods: Override inherited-method inclusion.
            include_classmethods: Override classmethod inclusion.
            expand_model_params: Override model expansion toggle.
            model_expansion_max_depth: Override model expansion depth.
            abbreviation_scope: Override abbreviation scope.
            executable_flags: Zero-argument executable flags for this command node.
            help_option_sort: Override help option sort rules.
            help_subcommand_sort: Override help subcommand sort rules.
            help_group: Optional help-only command group heading.

        Returns:
            A decorator that registers the callable and returns it unchanged.
        """

        def decorator(func: F) -> F:
            self.add_command(
                command=func,
                name=name,
                description=description,
                aliases=aliases,
                pipe_targets=pipe_targets,
                include_inherited_methods=include_inherited_methods,
                include_classmethods=include_classmethods,
                expand_model_params=expand_model_params,
                model_expansion_max_depth=model_expansion_max_depth,
                abbreviation_scope=abbreviation_scope,
                executable_flags=executable_flags,
                help_option_sort=help_option_sort,
                help_subcommand_sort=help_subcommand_sort,
                help_group=help_group,
            )
            return func

        return decorator

    def add_group(
        self,
        group: "CommandGroup",
        name: str | None = None,
        description: str | None = None,
        aliases: Sequence[str] | None = None,
        include_inherited_methods: bool | None = None,
        include_classmethods: bool | None = None,
        expand_model_params: bool | None = None,
        model_expansion_max_depth: int | None = None,
        abbreviation_scope: AbbreviationScope | None = None,
        executable_flags: list[ExecutableFlag] | None = None,
        help_option_sort: list[HelpOptionSortRule] | None = None,
        help_subcommand_sort: list[HelpSubcommandSortRule] | None = None,
        help_group: str | None = None,
    ) -> "Command":
        """
        Add a CommandGroup to the parser for deeply nested CLI structures.

        Args:
            group: The CommandGroup to add
            name: Override the group name
            description: Override the description
            aliases: Alternative names for this group
            include_inherited_methods: Override inherited-method inclusion.
            include_classmethods: Override classmethod inclusion.
            expand_model_params: Override model expansion toggle.
            model_expansion_max_depth: Override model expansion depth.
            abbreviation_scope: Override abbreviation scope.
            executable_flags: Zero-argument executable flags for this group node.
            help_option_sort: Override help option sort rules.
            help_subcommand_sort: Override help subcommand sort rules.
            help_group: Optional help-only command group heading.

        Returns:
            The Command schema for the group
        """
        combined_aliases: list[str] = list(aliases or [])
        for alias in group.aliases:
            if alias not in combined_aliases:
                combined_aliases.append(alias)

        canonical_name, command_aliases = self.name_registry.register(
            default_name=group.name,
            explicit_name=name,
            aliases=combined_aliases or None,
        )

        if canonical_name in self.commands:
            raise DuplicateCommandError(canonical_name)

        resolved_settings = self._resolve_command_settings(
            abbreviation_scope=abbreviation_scope,
            executable_flags=executable_flags,
            help_option_sort=help_option_sort,
            help_subcommand_sort=help_subcommand_sort,
            model_expansion_max_depth=model_expansion_max_depth,
            help_group=help_group,
        )

        builder = ParserSchemaBuilder(self)
        command = builder.build_from_group(
            group,
            canonical_name=canonical_name,
            include_inherited_methods=include_inherited_methods,
            include_classmethods=include_classmethods,
            expand_model_params=expand_model_params,
            **resolved_settings,
        )

        if description is not None:
            command.raw_description = description

        command.aliases = tuple(command_aliases)
        self._apply_command_settings(
            command,
            include_inherited_methods=include_inherited_methods,
            include_classmethods=include_classmethods,
            expand_model_params=expand_model_params,
            **resolved_settings,
        )
        self.commands[canonical_name] = command
        logger.debug("Added group: %s", command)
        return command

    def get_commands(self) -> list["Command"]:
        return list(self.commands.values())

    def get_command_by_cli_name(self, cli_name: str) -> "Command":
        """
        Return the command for a CLI name or alias.

        Args:
            cli_name (str): CLI name to resolve.

        Raises:
            InvalidCommandError: If the name cannot be resolved.
        """
        canonical = self.name_registry.canonical_for(cli_name)
        if canonical is None:
            raise InvalidCommandError(cli_name)
        return self.commands[canonical]

    def get_args(self) -> list[str]:
        return sys.argv[1:]

    def _set_runtime_process_title(self) -> None:
        """Best-effort process title update for terminal and multiplexer integrations."""
        set_process_title_from_argv()

    def exit(self, code: ExitCode) -> ExitCode:
        """
        Exit or return the provided code depending on configuration.

        Args:
            code (ExitCode): Exit code to use.
        """
        logger.info("Exit code: %s", code)
        if self.sys_exit_enabled:
            sys.exit(code)
        return code

    def pipe_to(
        self,
        targets: PipeTargets | dict[str, Any] | Sequence[str] | str,
        *,
        command: str | None = None,
        subcommand: str | None = None,
        **normalization_kwargs: object,
    ) -> PipeTargets:
        """
        Configure default pipe targets.

        If ``command`` is provided, the configuration applies only to that command name
        (and optionally one of its subcommands). Otherwise it becomes the global default
        for commands without an explicit override.
        """
        if "precedence" in normalization_kwargs and "priority" not in normalization_kwargs:
            normalization_kwargs["priority"] = normalization_kwargs.pop("precedence")
        config = build_pipe_targets_config(targets, **normalization_kwargs)
        if command is None:
            self.pipe_targets_default = config
        else:
            self._pipe_target_overrides[(command, subcommand)] = config
        return config

    def resolve_pipe_targets(
        self,
        command: "Command",
        *,
        subcommand: str | None = None,
    ) -> PipeTargets | None:
        """
        Resolve pipe target configuration for a command.

        Args:
            command (Command): Command schema to resolve.
            subcommand (str | None): Optional subcommand name.
        """
        names: list[str] = []
        if command.canonical_name:
            names.append(command.canonical_name)
        if command.cli_name and command.cli_name not in names:
            names.append(command.cli_name)
        if command.obj is not None and command.obj.name not in names:
            names.append(command.obj.name)

        for alias in command.aliases:
            if alias not in names:
                names.append(alias)

        for key in self._iter_pipe_override_keys_for_names(names, subcommand):
            config = self._pipe_target_overrides.get(key)
            if config is not None:
                return config

        return self.pipe_targets_default

    def _iter_pipe_override_keys_for_names(
        self,
        names: list[str],
        subcommand: str | None,
    ) -> Iterable[tuple[str | None, str | None]]:
        sub_candidates: list[str | None] = [subcommand]
        if subcommand is not None:
            alt = self.flag_strategy.command_translator.reverse(subcommand)
            if alt != subcommand:
                sub_candidates.append(alt)

        for name in names:
            for sub in sub_candidates:
                yield (name, sub)

        yield (None, subcommand)
        if subcommand is not None:
            alt = self.flag_strategy.command_translator.reverse(subcommand)
            if alt != subcommand:
                yield (None, alt)

        yield (None, None)

    def resolve_pipe_targets_by_names(
        self,
        *,
        canonical_name: str,
        obj_name: str | None,
        aliases: tuple[str, ...] = (),
        subcommand: str | None = None,
        include_default: bool = True,
    ) -> PipeTargets | None:
        """
        Resolve pipe targets by name variants and aliases.

        Args:
            canonical_name (str): Canonical command name.
            obj_name (str | None): Object name to match.
            aliases (tuple[str, ...]): Alternative names to match.
            subcommand (str | None): Optional subcommand name.
            include_default (bool): Whether to fall back to defaults.
        """
        names: list[str] = [canonical_name]
        if obj_name and obj_name not in names:
            names.append(obj_name)

        for alias in aliases:
            if alias not in names:
                names.append(alias)

        for key in self._iter_pipe_override_keys_for_names(names, subcommand):
            config = self._pipe_target_overrides.get(key)
            if config is not None:
                return config

        return self.pipe_targets_default if include_default else None

    def read_piped_input(self) -> str | None:
        """Read and cache stdin content if available."""
        if self._pipe_buffer is PIPE_UNSET:
            piped = read_piped()
            self._pipe_buffer = piped or None

        buffer = self._pipe_buffer
        if buffer is PIPE_UNSET:
            return None
        if buffer is None or isinstance(buffer, str):
            return buffer
        return None

    def reset_piped_input(self) -> None:
        """Clear any cached stdin content."""
        self._pipe_buffer = PIPE_UNSET

    def get_parameters_for(
        self,
        command: "Command",
        *,
        subcommand: str | None = None,
    ) -> dict[str, Parameter]:
        """
        Return parameter metadata for a command or subcommand.

        Args:
            command (Command): Command schema to inspect.
            subcommand (str | None): Optional subcommand name.
        """
        obj = command.obj

        if isinstance(obj, (Function, Method)):
            params = obj.params
        elif isinstance(obj, Class):
            if subcommand in (None, "__init__"):
                if obj.init_method is None:
                    return {}
                params = obj.init_method.params
            else:
                method = self._resolve_class_method(obj, subcommand)
                params = method.params
        else:
            return {}

        return {param.name: param for param in params}

    def _resolve_class_method(self, cls: Class, subcommand: str | None) -> Method:
        if subcommand is None:
            raise ConfigurationError("Subcommand name is required for class pipe targets")

        if subcommand == "__init__":
            if cls.init_method is None:
                raise ConfigurationError("Class does not define an __init__ method")
            return cls.init_method

        for method in cls.methods:
            if method.name == subcommand:
                return method

            translated = self.flag_strategy.command_translator.translate(method.name)
            if translated == subcommand:
                return method

        raise ConfigurationError(
            f"Could not resolve subcommand '{subcommand}' for class '{cls.name}'"
        )

    def parser_from_command(
        self,
        command: Function | Method | Class,
        main: bool = False,  # noqa: ARG002 - reserved API parameter
    ) -> object:
        """
        Build a parser object from an inspected command.

        Args:
            command (Function | Method | Class): Inspected command object.
            main (bool): Whether this is the main parser instance.
        """
        resolve_objinspect_annotations(command)
        if isinstance(command, (Function, Method)):
            return self.parser_from_function(command, taken_flags=[*self.RESERVED_FLAGS])
        if isinstance(command, Class):
            return self.parser_from_class(command)
        raise InvalidCommandError(command)

    def _should_skip_method(self, method: Method) -> bool:
        return method.name.startswith("_")

    def parse_args(self, args: list[str] | None = None) -> dict[str, Any]:
        """
        Parse CLI args into a nested dict keyed by command name.

        Args:
            args (list[str] | None): Argument list to parse. Defaults to sys.argv.
        """
        raise NotImplementedError

    def run(self, *commands: Callable[..., object], args: list[str] | None = None) -> object:
        """
        Register commands, parse args, and execute the selected command.

        Args:
            *commands (Callable): Commands to register.
            args (list[str] | None): Argument list to parse. Defaults to sys.argv.
        """
        raise NotImplementedError

    @abstractmethod
    def parser_from_function(self, *args: object, **kwargs: object) -> object:
        """
        Build a parser from a function or method.

        Args:
            *args (Any): Positional arguments forwarded to the implementation.
            **kwargs (Any): Keyword arguments forwarded to the implementation.
        """
        ...

    @abstractmethod
    def parser_from_class(self, *args: object, **kwargs: object) -> object:
        """
        Build a parser from a class command.

        Args:
            *args (Any): Positional arguments forwarded to the implementation.
            **kwargs (Any): Keyword arguments forwarded to the implementation.
        """
        ...

    @abstractmethod
    def parser_from_multiple_commands(self, *args: object, **kwargs: object) -> object:
        """
        Build a parser from multiple commands.

        Args:
            *args (Any): Positional arguments forwarded to the implementation.
            **kwargs (Any): Keyword arguments forwarded to the implementation.
        """
        ...

    @abstractmethod
    def install_tab_completion(self, *args: object, **kwargs: object) -> None:
        """
        Install tab completion for a parser instance.

        Args:
            *args (Any): Positional arguments forwarded to the implementation.
            **kwargs (Any): Keyword arguments forwarded to the implementation.
        """
        ...

    def log(self, message: str) -> None:
        """Log an informational message using the console helpers."""
        console.log(self.logger_message_tag, message)

    def log_error(self, message: str) -> None:
        """Log an error message using the console helpers."""
        console.log_error(self.logger_message_tag, message)

    def log_exception(self, e: BaseException) -> None:
        """Log an exception using the console helpers."""
        console.log_exception(self.logger_message_tag, e, full_traceback=self.full_error_traceback)

    def log_interrupt(self) -> None:
        """Log a message when the CLI is interrupted by user."""
        console.log_interrupt(silent=self.silent_interrupt)

    def build_parser_schema(self) -> "ParserSchema":
        """Build and return a ParserSchema for current commands."""
        builder = ParserSchemaBuilder(self)
        return builder.build()

    def get_last_schema(self) -> "ParserSchema | None":
        """
        Return the most recently built parser schema, if available.

        Backends can override this to expose cached schema state to shared runtime
        components without relying on private attributes.
        """
        return None


__all__ = ["ExitCode", "InterfacyParser"]

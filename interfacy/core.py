import sys
from abc import abstractmethod
from collections.abc import Callable, Iterable, Sequence
from enum import IntEnum, auto
from typing import TYPE_CHECKING, Any, ClassVar, Final

from objinspect import Class, Function, Method, Parameter, inspect
from objinspect.typing import type_name
from stdl.fs import read_piped
from stdl.st import colored, terminal_link
from strto import StrToTypeParser, get_parser

from interfacy.appearance.layout import HelpLayout, InterfacyLayout
from interfacy.exceptions import ConfigurationError, DuplicateCommandError, InvalidCommandError
from interfacy.logger import get_logger
from interfacy.naming import (
    AbbreviationGenerator,
    CommandNameRegistry,
    DefaultAbbreviationGenerator,
    DefaultFlagStrategy,
    FlagStrategy,
)
from interfacy.pipe import PipeTargets, build_pipe_targets_config
from interfacy.schema.builder import ParserSchemaBuilder

if TYPE_CHECKING:
    from interfacy.schema.schema import Command, ParserSchema


COMMAND_KEY: Final[str] = "command"
PIPE_UNSET = ...

logger = get_logger(__name__)


class ExitCode(IntEnum):
    SUCCESS = 0
    ERR_INVALID_ARGS = auto()
    ERR_PARSING = auto()
    ERR_RUNTIME = auto()
    ERR_RUNTIME_INTERNAL = auto()


class InterfacyParser:
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
        run: bool = False,
        print_result: bool = False,
        tab_completion: bool = False,
        full_error_traceback: bool = False,
        allow_args_from_file: bool = True,
        sys_exit_enabled: bool = True,
        flag_strategy: FlagStrategy | None = None,
        abbreviation_gen: AbbreviationGenerator | None = None,
        pipe_targets: PipeTargets | dict[str, Any] | Sequence[Any] | str | None = None,
        print_result_func: Callable = print,
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

        self.autorun = run
        self.allow_args_from_file = allow_args_from_file
        self.full_error_traceback = full_error_traceback
        self.enable_tab_completion = tab_completion
        self.sys_exit_enabled = sys_exit_enabled
        self.display_result = print_result

        self.abbreviation_gen = abbreviation_gen or DefaultAbbreviationGenerator()
        self.type_parser = type_parser or get_parser(from_file=allow_args_from_file)
        self.flag_strategy = flag_strategy or DefaultFlagStrategy()
        self.help_layout = help_layout or InterfacyLayout()
        self.help_layout.flag_generator = self.flag_strategy
        self.name_registry = CommandNameRegistry(self.flag_strategy.command_translator)
        self.help_layout.name_registry = self.name_registry

        self.commands: dict[str, Command] = {}

    def add_command(
        self,
        command: Callable | Any,
        name: str | None = None,
        description: str | None = None,
        aliases: Sequence[str] | None = None,
        pipe_targets: PipeTargets | dict[str, Any] | Sequence[str] | str | None = None,
    ) -> "Command":
        obj = inspect(command, inherited=False)

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
        self.commands[canonical_name] = command
        logger.debug(f"Added command: {command}")
        return command

    def get_commands(self) -> list["Command"]:
        return list(self.commands.values())

    def get_command_by_cli_name(self, cli_name: str) -> "Command":
        canonical = self.name_registry.canonical_for(cli_name)
        if canonical is None:
            raise InvalidCommandError(cli_name)
        return self.commands[canonical]

    def get_args(self) -> list[str]:
        return sys.argv[1:]

    def exit(self, code: ExitCode) -> ExitCode:
        logger.info(f"Exit code: {code}")
        if self.sys_exit_enabled:
            sys.exit(code)
        return code

    def pipe_to(
        self,
        targets,
        *,
        command: str | None = None,
        subcommand: str | None = None,
        **normalization_kwargs,
    ) -> PipeTargets:
        """Configure default pipe targets.

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
        names: list[str] = []
        if command.canonical_name:
            names.append(command.canonical_name)
        if command.cli_name and command.cli_name not in names:
            names.append(command.cli_name)
        if command.obj.name not in names:
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
        if self._pipe_buffer is PIPE_UNSET:
            piped = read_piped()
            self._pipe_buffer = piped if piped else None

        return self._pipe_buffer if self._pipe_buffer is not PIPE_UNSET else None

    def reset_piped_input(self) -> None:
        self._pipe_buffer = PIPE_UNSET

    def get_parameters_for(
        self,
        command: "Command",
        *,
        subcommand: str | None = None,
    ) -> dict[str, Parameter]:
        obj = command.obj

        if isinstance(obj, Function):
            params = obj.params
        elif isinstance(obj, Method):
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

    def parser_from_command(self, command: Function | Method | Class, main: bool = False) -> Any:
        if isinstance(command, (Function, Method)):
            return self.parser_from_function(command, taken_flags=[*self.RESERVED_FLAGS])
        if isinstance(command, Class):
            return self.parser_from_class(command)
        raise InvalidCommandError(command)

    def _should_skip_method(self, method: Method) -> bool:
        return method.name.startswith("_")

    def parse_args(self, args: list[str] | None = None) -> dict[str, Any]:
        raise NotImplementedError

    def run(self, *commands: Callable, args: list[str] | None = None) -> Any:
        raise NotImplementedError

    @abstractmethod
    def parser_from_function(self, *args, **kwargs) -> Any: ...

    @abstractmethod
    def parser_from_class(self, *args, **kwargs) -> Any: ...

    @abstractmethod
    def parser_from_multiple_commands(self, *args, **kwargs) -> Any: ...

    @abstractmethod
    def install_tab_completion(self, *args, **kwargs) -> None: ...

    def log(self, message: str) -> None:
        print(f"[{self.logger_message_tag}] {message}", file=sys.stdout)

    def log_error(self, message: str) -> None:
        message = f"[{self.logger_message_tag}] {message}"
        message = colored(message, color="red")
        print(message, file=sys.stderr)

    def log_exception(self, e: Exception) -> None:
        import sys
        import traceback

        if self.full_error_traceback:
            print(traceback.format_exc(), file=sys.stderr)

        message = ""
        tb = e.__traceback__

        exception_str = type_name(str(type(e))) + ": " + str(e)
        if tb:
            file_info = f"{terminal_link(tb.tb_frame.f_code.co_filename)}:{tb.tb_lineno}"
            message += file_info
            message += " "

        message += f"{colored(exception_str, color='red')}"
        message = f"[{self.logger_message_tag}] {message}"
        message = colored(message, color="red")
        print(message, file=sys.stderr)

    def build_parser_schema(self) -> "ParserSchema":
        builder = ParserSchemaBuilder(self)
        return builder.build()


__all__ = ["InterfacyParser", "ExitCode"]

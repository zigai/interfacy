from __future__ import annotations

import argparse
import sys
from argparse import Namespace
from collections.abc import Sequence
from copy import deepcopy
from gettext import gettext
from typing import TYPE_CHECKING, Any, NoReturn

from interfacy.backends.argparse.argument_kwargs import (
    callable_type_name,
    normalize_argument_kwargs,
)
from interfacy.backends.argparse.errors import ArgparseParseError, is_missing_subcommand_error
from interfacy.backends.argparse.help_schema import (
    help_argument_from_actions,
    implicit_command,
)
from interfacy.backends.argparse.namespaces import (
    DEST_KEY,
    container_actions,
    container_defaults,
    deflatten_namespace,
    extract_destination,
    nested_destination,
    original_destination,
)
from interfacy.common.debug import get_logger
from interfacy.exceptions import InterfacyExit, UsageError
from interfacy.help import StandardLayout
from interfacy.help.content import HelpRenderer
from interfacy.help.renderer import (
    SchemaHelpRenderer,
)
from interfacy.schema.model import SUBCOMMANDS_KEY

if TYPE_CHECKING:
    from interfacy.backends.base import HelpPipeline
    from interfacy.help import HelpLayout
    from interfacy.schema.model import Argument, Command, ParserSchema

logger = get_logger(__name__)


class NestedSubParsersAction(argparse._SubParsersAction):  # type: ignore[private-member-access]
    """
    Subparser action that supports nested destination paths.

    Args:
        option_strings (list[str]): Option strings that trigger the action.
        prog (str): Program name for help output.
        base_nest_path (list[str]): Base nesting path components.
        nest_separator (str): Separator for nested destination keys.
        parser_class (type[ArgumentParser] | None): Parser class for children.
        dest (str): Destination key for the subparser.
        required (bool): Whether a subcommand is required.
        help (str | None): Help text for the action.
        metavar (str | None): Metavar for help output.
        help_layout (Any | None): Layout configuration passed to children.
        sys_exit_enabled (bool): Exit policy passed to children.
        supplied_dests (set[str] | None): Supplied-destination record shared with children.
    """

    def __init__(
        self,
        option_strings: list[str],
        prog: str,
        base_nest_path: list[str],
        nest_separator: str,
        parser_class: type[ArgumentParser] | None = None,
        dest: str = argparse.SUPPRESS,
        required: bool = False,
        help: str | None = None,  # noqa: A002 - argparse API compatibility
        metavar: str | None = None,
        help_layout: HelpLayout | None = None,
        help_renderer: HelpRenderer | None = None,
        help_flags: Sequence[str] = ("--help",),
        sys_exit_enabled: bool = True,
        supplied_dests: set[str] | None = None,
    ) -> None:
        super().__init__(
            option_strings,
            prog,
            parser_class or ArgumentParser,
            dest=dest,
            required=required,
            help=help,
            metavar=metavar,
        )

        self.base_nest_path_components = base_nest_path
        self.nest_separator = nest_separator
        self._child_help_layout = help_layout
        self._child_help_renderer = help_renderer
        self._child_help_flags = tuple(help_flags)
        self._child_sys_exit_enabled = sys_exit_enabled
        self._child_supplied_dests = supplied_dests

    def add_parser(  # type: ignore[override]
        self,
        name: str,
        *,
        help: str | None = None,  # noqa: A002 - argparse API compatibility
        aliases: Sequence[str] = (),
        prog: str | None = None,
        usage: str | None = None,
        description: str | None = None,
        epilog: str | None = None,
        parents: Sequence[argparse.ArgumentParser] = (),
        prefix_chars: str = "-",
        fromfile_prefix_chars: str | None = None,
        argument_default: Any = None,
        conflict_handler: str = "error",
        add_help: bool = True,
        allow_abbrev: bool = True,
        exit_on_error: bool = True,
        nest_dir: str | None = None,
        **kwargs: Any,
    ) -> ArgumentParser:
        """
        Creates and returns a new parser for a subcommand with nesting support.

        Args:
            name (str): Name of the subcommand.
            help (str | None, optional): Help message for the subcommand. Defaults to None.
            aliases (Sequence[str], optional): Alternative names for the subcommand. Defaults to ().
            prog (str | None, optional): Program name. Defaults to None.
            usage (str | None, optional): Usage message. Defaults to None.
            epilog (str | None, optional): Text following the argument descriptions. Defaults to None.
            description (str | None, optional): Description shown before the subparser's arguments. Defaults to None.
            parents (Sequence[ArgumentParser], optional): Parent parsers. Defaults to ().
            prefix_chars (str, optional): Characters that prefix optional arguments. Defaults to "-".
            fromfile_prefix_chars (str | None, optional): Characters prefixing files with arguments. Defaults to None.
            argument_default (Any, optional): Default value for all arguments. Defaults to None.
            conflict_handler (str, optional): How to handle conflicts. Defaults to "error".
            add_help (bool, optional): Add a --help option. Defaults to True.
            allow_abbrev (bool, optional): Allow abbreviated long options. Defaults to True.
            exit_on_error (bool, optional): Exit with error info on error. Defaults to True.
            nest_dir (str | None, optional): Custom nesting directory name. Defaults to name if not provided.
            **kwargs: Additional arguments passed to parent class.

        Returns:
            NestedArgumentParser: A new parser for the subcommand.
        """
        kwargs.setdefault("help_layout", self._child_help_layout)
        kwargs.setdefault("help_renderer", self._child_help_renderer)
        kwargs.setdefault("sys_exit_enabled", self._child_sys_exit_enabled)
        kwargs.setdefault("supplied_dests", self._child_supplied_dests)
        nested_components = [*self.base_nest_path_components]
        if nested_components:
            nested_components.extend([SUBCOMMANDS_KEY, nest_dir or name])
        else:
            nested_components.append(nest_dir or name)

        parser: ArgumentParser = super().add_parser(  # type: ignore[assignment]
            name,
            help=help,
            aliases=aliases,
            prog=prog,
            usage=usage,
            description=description,
            epilog=epilog,
            parents=parents,
            prefix_chars=prefix_chars,
            fromfile_prefix_chars=fromfile_prefix_chars,
            argument_default=argument_default,
            conflict_handler=conflict_handler,
            add_help=add_help,
            allow_abbrev=allow_abbrev,
            nest_path=nested_components,
            nest_separator=self.nest_separator,
            exit_on_error=exit_on_error,
            help_flags=self._child_help_flags,
            **kwargs,
        )
        return parser


class ArgumentParser(argparse.ArgumentParser):
    """
    ArgumentParser with nested destinations and custom help formatting.

    Args:
        prog (str | None): Program name used in help output.
        usage (str | None): Custom usage string.
        description (str | None): Description text shown in help.
        epilog (str | None): Epilog text shown after help.
        parents (list[argparse.ArgumentParser] | None): Parent parsers to inherit args.
        prefix_chars (str): Prefix characters for options.
        fromfile_prefix_chars (str | None): Prefix for args-from-file.
        argument_default (Any): Default value for all arguments.
        conflict_handler (str): Conflict resolution strategy.
        add_help (bool): Whether to add a help option.
        allow_abbrev (bool): Whether to allow abbreviations of long options.
        nest_dir (str | None): Base nesting directory label.
        nest_separator (str): Separator for nested destinations.
        nest_path (list[str] | None): Explicit nesting path components.
        exit_on_error (bool): Whether to exit on parse errors.
        help_layout (Any | None): Layout configuration for help rendering.
        help_position (int | None): Absolute column where help descriptions begin.
        color (bool | None): Force colorized help output when supported.
        sys_exit_enabled (bool): Exit the process after help and usage errors, like
            argparse. When False, raise InterfacyExit or UsageError instead.
        supplied_dests (set[str] | None): Record of destinations given on the command line,
            shared with nested subparsers.
    """

    def __init__(
        self,
        prog: str | None = None,
        usage: str | None = None,
        description: str | None = None,
        epilog: str | None = None,
        parents: list[argparse.ArgumentParser] | None = None,
        prefix_chars: str = "-",
        fromfile_prefix_chars: str | None = None,
        argument_default: Any = None,
        conflict_handler: str = "error",
        add_help: bool = True,
        allow_abbrev: bool = True,
        nest_dir: str | None = None,
        nest_separator: str = "__",
        nest_path: list[str] | None = None,
        exit_on_error: bool = True,
        *,
        help_layout: HelpLayout | None = None,
        help_position: int | None = None,
        help_flags: Sequence[str] = ("--help",),
        color: bool | None = None,
        help_renderer: HelpRenderer | None = None,
        sys_exit_enabled: bool = True,
        supplied_dests: set[str] | None = None,
    ) -> None:
        if parents is None:
            parents = []

        self.nest_path_components = nest_path or ([nest_dir] if nest_dir else [])
        self.nest_dir = self.nest_path_components[-1] if self.nest_path_components else None
        self.nest_separator = nest_separator
        self._original_destinations: dict[str, str] = {}  # nested_dest: original_dest

        base_init_kwargs: dict[str, Any] = {
            "prog": prog,
            "usage": usage,
            "description": description,
            "epilog": epilog,
            "parents": parents,
            "formatter_class": argparse.HelpFormatter,
            "prefix_chars": prefix_chars,
            "fromfile_prefix_chars": fromfile_prefix_chars,
            "argument_default": argument_default,
            "conflict_handler": conflict_handler,
            "add_help": False,
            "exit_on_error": exit_on_error,
            "allow_abbrev": allow_abbrev,
        }

        if color is None and sys.version_info >= (3, 14):
            color = False

        if color is not None:
            base_init_kwargs["color"] = color

        try:
            super().__init__(**base_init_kwargs)
        except TypeError as exc:
            if "color" not in base_init_kwargs or "color" not in str(exc):
                raise

            base_init_kwargs.pop("color")
            super().__init__(**base_init_kwargs)

        self._interfacy_help_layout = (
            deepcopy(help_layout)
            if help_layout is not None
            else StandardLayout(include_metavar_in_flag_display=True)
        )
        if help_position is not None:
            self._interfacy_help_layout.help_position = help_position

        self._schema_command: Command | None = None
        self._schema: ParserSchema | None = None
        self.help_renderer = help_renderer
        self._help_pipeline: HelpPipeline | None = None
        self._help_command_path: tuple[str, ...] = ()
        self._interfacy_raise_parse_errors = False
        self.sys_exit_enabled = sys_exit_enabled
        # Shared with every nested subparser; the owner clears it before each parse.
        self.supplied_dests = set() if supplied_dests is None else supplied_dests
        self.add_help = add_help
        self.help_flags = tuple(help_flags)

        if add_help:
            if "-" in self.prefix_chars:
                help_flags_to_add = [flag for flag in self.help_flags if flag.startswith("-")] or [
                    "--help"
                ]
            else:
                default_prefix = self.prefix_chars[0]
                help_flags_to_add = [default_prefix * 2 + "help"]

            self.add_argument(
                *help_flags_to_add,
                action="help",
                default=argparse.SUPPRESS,
                help=gettext("Show this help message and exit"),
            )

        self.register("action", "parsers", NestedSubParsersAction)

    def format_help(self) -> str:
        """Render all generated and manual help through the structured pipeline."""
        if self._help_pipeline is not None:
            return self._help_pipeline.render(self._help_command_path)

        renderer = SchemaHelpRenderer(
            self._interfacy_help_layout,
            help_argument=self._get_help_argument_for_schema(),
            final_renderer=self.help_renderer,
        )
        if self._schema is not None:
            return renderer.render_parser_help(self._schema, self.prog)
        if self._schema_command is not None:
            return renderer.render_command_help(self._schema_command, self.prog)
        return renderer.render_command_help(self._build_implicit_schema_command(), self.prog)

    def set_help_pipeline(
        self,
        pipeline: HelpPipeline,
        command_path: tuple[str, ...],
    ) -> None:
        """Attach the engine-owned structured help pipeline."""
        self._help_pipeline = pipeline
        self._help_command_path = command_path

    def set_schema_command(self, command: Command | None) -> None:
        """
        Store the active command schema for schema-aware help rendering.

        Args:
            command (Command | None): Command schema tied to this parser.
        """
        self._schema_command = command

    def set_schema(self, schema: ParserSchema | None) -> None:
        """
        Store the parser schema for schema-aware help rendering.

        Args:
            schema (ParserSchema | None): Full parser schema tied to this parser.
        """
        self._schema = schema

    def add_subparsers(self, **kwargs: Any) -> NestedSubParsersAction:
        """
        Create a nested subparser group with remapped destinations.

        Args:
            **kwargs (Any): Arguments forwarded to argparse add_subparsers.
        """
        logger.info("Adding subparsers with kwarg keys=%s", sorted(kwargs))

        if DEST_KEY in kwargs:
            dest = kwargs[DEST_KEY]
            nested_dest = self._get_nested_destination(dest.replace("-", "_"), store=True)
            kwargs[DEST_KEY] = nested_dest

        kwargs.update(
            {
                "base_nest_path": self.nest_path_components,
                "nest_separator": self.nest_separator,
                "help_layout": self._interfacy_help_layout,
                "help_flags": self.help_flags,
                "help_renderer": self.help_renderer,
                "sys_exit_enabled": self.sys_exit_enabled,
                "supplied_dests": self.supplied_dests,
            }
        )

        action = super().add_subparsers(**kwargs)
        if not isinstance(action, NestedSubParsersAction):
            raise TypeError("Nested subparser factory returned an unexpected action type")

        return action

    def parse_known_args(  # type: ignore[override]
        self,
        args: Sequence[str] | None = None,
        namespace: Namespace | None = None,
    ) -> tuple[Namespace, list[str]]:
        """
        Parse known args and deflatten nested destinations.

        Args:
            args (Sequence[str] | None): Argument list to parse. Defaults to sys.argv.
            namespace (Namespace | None): Optional namespace to populate.
        """
        if namespace is None:
            namespace = Namespace()

        parsed_args, unknown_args = super().parse_known_args(args=args, namespace=namespace)
        logger.info(
            "Initial parse keys: %s, unknown count=%d",
            sorted(vars(parsed_args)),
            len(unknown_args),
        )

        deflattened_args = self._deflatten_namespace(parsed_args)
        logger.info("Deflattened keys: %s", sorted(vars(deflattened_args)))

        return deflattened_args, unknown_args

    def set_defaults(self, **kwargs: Any) -> None:
        """
        Set defaults while respecting nested destinations.

        Args:
            **kwargs (Any): Default values keyed by original destination names.
        """
        nested_kwargs = {
            self._get_nested_destination(dest, store=True): value for dest, value in kwargs.items()
        }
        logger.info("Nested default keys: %s", sorted(nested_kwargs))
        super().set_defaults(**nested_kwargs)

    def get_default(self, dest: str) -> Any:
        """
        Return the default value for a destination name.

        Args:
            dest (str): Original destination name.
        """
        nested_dest = self._get_nested_destination(dest)
        value = super().get_default(nested_dest)

        return value

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        """Exit the process, or raise when process exit is disabled."""
        if self.sys_exit_enabled:
            super().exit(status, message)

        if status == 0:
            raise InterfacyExit()

        raise UsageError((message or "").strip(), usage=self.format_usage())

    def error(self, message: str) -> NoReturn:
        """Report a usage failure by exiting with status 2 or raising a structured error."""
        usage = self.format_usage()
        if is_missing_subcommand_error(message, self._actions, self._original_destinations):
            usage = self.format_help()

        if self._interfacy_raise_parse_errors:
            raise ArgparseParseError(message, usage=usage)

        if not self.sys_exit_enabled:
            raise UsageError(message, usage=usage)

        self._print_message(f"{usage.rstrip()}\n", sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n")

    def _get_formatter(self) -> argparse.HelpFormatter:  # type: ignore[override]
        formatter = super()._get_formatter()
        set_color = getattr(formatter, "_set_color", None)
        if callable(set_color):
            set_color(getattr(self, "color", False))

        return formatter

    def _get_help_argument_for_schema(self) -> Argument | None:
        return help_argument_from_actions(self._actions)

    def _build_implicit_schema_command(self) -> Command:
        if self._interfacy_help_layout is None:
            raise ValueError("Cannot synthesize a schema command without a help layout.")

        return implicit_command(
            self._actions,
            prog=self.prog,
            description=self.description,
            epilog=self.epilog,
            dest_name=self._original_dest_name,
            child_command=self._child_schema_command,
        )

    @staticmethod
    def _child_schema_command(parser: argparse.ArgumentParser) -> Command | None:
        if not isinstance(parser, ArgumentParser):
            return None

        return parser._build_implicit_schema_command()

    def _original_dest_name(self, dest: str) -> str:
        return original_destination(dest, self._original_destinations, self.nest_separator)

    def _add_container_actions(self, container: argparse._ActionsContainer) -> None:
        self._remap_container_destinations(container)
        return super()._add_container_actions(container)

    def _get_positional_kwargs(self, dest: str, **kwargs: Any) -> dict[str, Any]:
        logger.debug("Getting positional kwargs for dest='%s'", dest)
        nested_dest = self._get_nested_destination(dest.replace("-", "_"), store=True)
        kwargs = self._edit_arguments(dest, **kwargs)

        return super()._get_positional_kwargs(nested_dest, **kwargs)

    def _get_optional_kwargs(self, *args: str, **kwargs: Any) -> dict[str, Any]:
        logger.debug("Getting optional kwargs for args=%s", args)
        dest = self._extract_destination(*args, **kwargs)
        nested_dest = self._get_nested_destination(dest.replace("-", "_"), store=True)
        kwargs[DEST_KEY] = nested_dest
        kwargs = self._edit_arguments(dest, **kwargs)

        return super()._get_optional_kwargs(*args, **kwargs)

    def _deflatten_namespace(self, namespace: Namespace) -> Namespace:
        return deflatten_namespace(namespace, self.nest_separator)

    def _remap_container_destinations(self, container: argparse._ActionsContainer) -> None:
        defaults = container_defaults(container)
        logger.info("Remapping container destination keys: %s", sorted(defaults))
        remapped_defaults = {
            self._get_nested_destination(dest): value for dest, value in defaults.items()
        }
        container._defaults = remapped_defaults
        logger.info("Remapped container destination keys: %s", sorted(remapped_defaults))

        for action in container_actions(container):
            self._remap_action_destinations(action)

    def _remap_action_destinations(self, action: argparse.Action) -> None:
        logger.info("Remapping action dest: %s", action.dest)

        if action.dest is not None:
            old_dest = action.dest
            action.dest = self._get_nested_destination(action.dest, store=True)
            logger.info("Remapped action dest from %s to %s", old_dest, action.dest)

        if isinstance(action, NestedSubParsersAction) and action.choices is not None:
            for subparser in action.choices.values():
                if isinstance(subparser, ArgumentParser):
                    self._remap_container_destinations(subparser)

    def _extract_destination(self, *args: str, **kwargs: Any) -> str:
        return extract_destination(args, kwargs.get(DEST_KEY), self.prefix_chars)

    def _get_nested_destination(self, dest: str, *, store: bool = False) -> str:
        nested = nested_destination(dest, self.nest_path_components, self.nest_separator)
        if store and self.nest_path_components:
            self._original_destinations[nested] = dest

        return nested

    def _edit_arguments(self, original_dest: str, **kwargs: Any) -> dict[str, Any]:
        return normalize_argument_kwargs(original_dest, self.nest_separator, kwargs)

    def _get_value(self, action: argparse.Action, arg_string: str) -> Any:
        parse_func = self._registry_get("type", action.type, action.type)
        if not callable(parse_func):
            raise argparse.ArgumentError(action, f"{parse_func!r} is not callable")

        try:
            result = parse_func(arg_string)

        except argparse.ArgumentTypeError as exc:
            raise argparse.ArgumentError(action, exc.args[0]) from exc

        except (TypeError, ValueError, KeyError) as exc:
            t_name = callable_type_name(parse_func, fallback="value")
            raise argparse.ArgumentError(action, f"invalid {t_name} value: '{arg_string}'") from exc

        return result

    def _get_values(self, action: argparse.Action, arg_strings: list[str]) -> Any:
        # argparse also calls this for absent optional positionals, with no strings.
        if action.option_strings or arg_strings:
            self.supplied_dests.add(action.dest)

        if (
            not arg_strings
            and action.nargs == argparse.ZERO_OR_MORE
            and not action.option_strings
            and action.choices is not None
        ):
            choices = action.choices
            action.choices = None
            try:
                return super()._get_values(action, arg_strings)
            finally:
                action.choices = choices

        return super()._get_values(action, arg_strings)


__all__ = [
    "ArgumentParser",
    "NestedSubParsersAction",
]

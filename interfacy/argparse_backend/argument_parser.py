import argparse
import sys
from argparse import Namespace
from collections.abc import Callable, Sequence
from typing import Any, Literal

from objinspect.typing import type_name

from interfacy.argparse_backend.help_formatter import InterfacyHelpFormatter
from interfacy.logger import get_logger

logger = get_logger(__name__)


DEST_KEY = "dest"
ActionType = Callable[[str], Any] | type[Any] | str | None
NargsPattern = Literal["?", "*", "+"]


def namespace_to_dict(namespace: Namespace) -> dict[str, Any]:
    result = {}
    for k, v in vars(namespace).items():
        if isinstance(v, Namespace):
            result[k] = namespace_to_dict(v)
        else:
            result[k] = v
    return result


class NestedSubParsersAction(argparse._SubParsersAction):
    def __init__(
        self,
        option_strings: list[str],
        prog: str,
        base_nest_path: list[str],
        nest_separator: str,
        parser_class: type["ArgumentParser"] | None = None,
        dest: str = argparse.SUPPRESS,
        required: bool = False,
        help: str | None = None,
        metavar: str | None = None,
        formatter_class: type[argparse.HelpFormatter] | None = None,
        help_layout: Any | None = None,
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
        self._child_formatter_class = formatter_class or InterfacyHelpFormatter
        self._child_help_layout = help_layout

    def add_parser(  # type: ignore
        self,
        name: str,
        *,
        help: str | None = None,
        aliases: Sequence[str] = (),
        prog: str | None = None,
        usage: str | None = None,
        description: str | None = None,
        epilog: str | None = None,
        parents: Sequence[argparse.ArgumentParser] = (),
        formatter_class: type[argparse.HelpFormatter] | None = None,
        prefix_chars: str = "-",
        fromfile_prefix_chars: str | None = None,
        argument_default: Any = None,
        conflict_handler: str = "error",
        add_help: bool = True,
        allow_abbrev: bool = True,
        exit_on_error: bool = True,
        nest_dir: str | None = None,
        **kwargs: Any,
    ) -> "ArgumentParser":
        """
        Creates and returns a new parser for a subcommand with nesting support.

        Args:
            name (str): Name of the subcommand.
            help (str | None, optional): Help message for the subcommand. Defaults to None.
            aliases (Sequence[str], optional): Alternative names for the subcommand. Defaults to ().
            prog (str | None, optional): Program name. Defaults to None.
            usage (str | None, optional): Usage message. Defaults to None.
            description (str | None, optional): Description of the subcommand. Defaults to None.
            epilog (str | None, optional): Text following the argument descriptions. Defaults to None.
            parents (Sequence[ArgumentParser], optional): Parent parsers. Defaults to ().
            formatter_class (Type[HelpFormatter], optional): Help message formatter. Defaults to HelpFormatter.
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

        return super().add_parser(
            name,
            help=help,
            aliases=aliases,
            prog=prog,
            usage=usage,
            description=description,
            epilog=epilog,
            parents=parents,
            formatter_class=formatter_class or self._child_formatter_class,
            prefix_chars=prefix_chars,
            fromfile_prefix_chars=fromfile_prefix_chars,
            argument_default=argument_default,
            conflict_handler=conflict_handler,
            add_help=add_help,
            allow_abbrev=allow_abbrev,
            nest_path=[*self.base_nest_path_components, nest_dir or name],
            nest_separator=self.nest_separator,
            exit_on_error=exit_on_error,
            **kwargs,
        )


class ArgumentParser(argparse.ArgumentParser):
    def __init__(
        self,
        prog: str | None = None,
        usage: str | None = None,
        description: str | None = None,
        epilog: str | None = None,
        parents: list[argparse.ArgumentParser] | None = None,
        formatter_class: type[argparse.HelpFormatter] = InterfacyHelpFormatter,
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
        help_layout: Any | None = None,
        color: bool | None = None,
    ) -> None:
        """
        Parser for converting command-line strings into Python objects.

        Args:
            prog (str, optional): The name of the program. Defaults to os.path.basename(sys.argv[0]).
            usage (str, optional): A usage message. If not provided, auto-generated from arguments.
            description (str, optional): A description of what the program does.
            epilog (str, optional): Text following the argument descriptions.
            parents (list[ArgumentParser], optional): Parsers whose arguments should be copied into this one.
            formatter_class (type[HelpFormatter], optional): HelpFormatter class for printing help messages.
            prefix_chars (str, optional): Characters that prefix optional arguments.
            fromfile_prefix_chars (str, optional): Characters that prefix files containing additional arguments.
            argument_default (Any, optional): The default value for all arguments.
            conflict_handler (str, optional): String indicating how to handle conflicts.
            add_help (bool, optional): Whether to add a --help option.
            allow_abbrev (bool, optional): Whether to allow long options to be abbreviated unambiguously.
            nest_dir (str | None, optional): Custom nesting directory name. Defaults to None.
            nest_separator (str, optional): Separator for nested arguments. Defaults to "__".
            nest_path (list[str] | None, optional): Path components for nested arguments. Defaults to None.
            exit_on_error (bool, optional): Whether ArgumentParser exits with error info when an error occurs.
            help_layout (HelpLayout | None, optional): Layout configuration for help text formatting. Defaults to None.
            color (bool | None, optional): Whether argparse should emit colorized help (Python >= 3.14). Defaults to None.
        """
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
            "formatter_class": formatter_class,
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
        self.add_help = add_help
        if add_help:
            if "-" in self.prefix_chars:
                help_flags = ["--help"]
            else:
                default_prefix = self.prefix_chars[0]
                help_flags = [default_prefix * 2 + "help"]

            self.add_argument(
                *help_flags,
                action="help",
                default=argparse.SUPPRESS,
                help=argparse._("show this help message and exit"),
            )
        self.register("action", "parsers", NestedSubParsersAction)
        self._interfacy_help_layout = help_layout

    def _get_formatter(self):  # type: ignore
        formatter = self.formatter_class(self.prog)  # type: ignore[arg-type]
        if hasattr(formatter, "set_help_layout"):
            try:
                formatter.set_help_layout(self._interfacy_help_layout)
            except Exception:
                pass
        if hasattr(formatter, "prepare_layout"):
            try:
                formatter.prepare_layout(self._actions)
            except Exception:
                pass
        return formatter

    def add_subparsers(self, **kwargs: Any) -> NestedSubParsersAction:
        logger.info(f"Adding subparsers with kwargs={kwargs}")
        if DEST_KEY in kwargs:
            dest = kwargs[DEST_KEY]
            nested_dest = self._get_nested_destination(dest.replace("-", "_"), store=True)
            kwargs[DEST_KEY] = nested_dest

        kwargs.update(
            {
                "base_nest_path": self.nest_path_components,
                "nest_separator": self.nest_separator,
                "formatter_class": self.formatter_class,
                "help_layout": getattr(self, "_interfacy_help_layout", None),
            }
        )
        return super().add_subparsers(**kwargs)  # type: ignore

    def parse_known_args(  # type: ignore
        self,
        args: Sequence[str] | None = None,
        namespace: Namespace | None = None,
    ) -> tuple[Namespace, list[str]]:
        parsed_args, unknown_args = super().parse_known_args(args=args, namespace=namespace)
        logger.info(f"Initial parse result: {vars(parsed_args)}, unknown={unknown_args}")
        if parsed_args is None:
            raise ValueError("No parsed arguments found.")

        deflattened_args = self._deflatten_namespace(parsed_args)
        logger.info(f"Deflattened result:   {vars(deflattened_args)}")
        return deflattened_args, unknown_args

    def set_defaults(self, **kwargs: Any) -> None:
        nested_kwargs = {
            self._get_nested_destination(dest, store=True): value for dest, value in kwargs.items()
        }
        logger.info(f"Nested defaults: {nested_kwargs}")
        super().set_defaults(**nested_kwargs)

    def get_default(self, dest: str) -> Any:
        nested_dest = self._get_nested_destination(dest)
        value = super().get_default(nested_dest)
        return value

    def _add_container_actions(self, container: argparse._ActionsContainer) -> None:
        self._remap_container_destinations(container)
        return super()._add_container_actions(container)

    def _get_positional_kwargs(self, dest: str, **kwargs: Any) -> dict[str, Any]:
        logger.debug(f"Getting positional kwargs for dest='{dest}'")
        nested_dest = self._get_nested_destination(dest.replace("-", "_"), store=True)
        kwargs = self._edit_arguments(dest, **kwargs)
        return super()._get_positional_kwargs(nested_dest, **kwargs)

    def _get_optional_kwargs(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        logger.debug(f"Getting optional kwargs for args={args}")
        dest = self._extract_destination(*args, **kwargs)
        nested_dest = self._get_nested_destination(dest.replace("-", "_"), store=True)
        kwargs[DEST_KEY] = nested_dest
        kwargs = self._edit_arguments(dest, **kwargs)
        return super()._get_optional_kwargs(*args, **kwargs)

    def _deflatten_namespace(self, namespace: Namespace) -> Namespace:
        root = Namespace()

        for key, value in vars(namespace).items():
            components = key.split(self.nest_separator)
            current = root

            # Navigate through component hierarchy
            for component in components[:-1]:
                if not hasattr(current, component):
                    logger.debug(f"Creating new namespace for '{component}'")
                    setattr(current, component, Namespace())
                current = getattr(current, component)

            # Set or merge final value
            final_component = components[-1]
            if hasattr(current, final_component):
                logger.warning(f"Handling conflict at {final_component}")
                existing_value = getattr(current, final_component)
                if isinstance(existing_value, Namespace) and isinstance(value, Namespace):
                    self._recursively_merge_namespaces(existing_value, value)
                else:
                    raise ValueError(f'Cannot merge namespaces due to conflict at key "{key}"')
            else:
                setattr(current, final_component, value)

        return root

    def _recursively_merge_namespaces(self, destination: Namespace, source: Namespace) -> Namespace:
        for name, value in vars(source).items():
            if hasattr(destination, name):
                dest_value = getattr(destination, name)
                if isinstance(dest_value, Namespace) and isinstance(value, Namespace):
                    logger.info(f"Recursively merging at attribute: {name}")
                    self._recursively_merge_namespaces(dest_value, value)
                else:
                    raise ValueError(
                        f'Cannot merge namespaces due to conflict at attribute "{name}".'
                    )
            else:
                logger.info(f"Setting new attribute: {name}={value}")
                setattr(destination, name, value)
        return destination

    def _remap_container_destinations(self, container: argparse._ActionsContainer) -> None:
        logger.info(f"Remapping container destinations: {container._defaults}")
        container._defaults = {
            self._get_nested_destination(dest): value for dest, value in container._defaults.items()
        }
        logger.info(f"Remapped container destinations: {container._defaults}")

        for action in container._actions:
            self._remap_action_destinations(action)

    def _remap_action_destinations(self, action: argparse.Action) -> None:
        logger.info(f"Remapping action: {action}")

        if action.dest is not None:
            old_dest = action.dest
            action.dest = self._get_nested_destination(action.dest, store=True)
            logger.info(f"Remapped action dest from {old_dest} to {action.dest}")

        if isinstance(action, NestedSubParsersAction) and action.choices is not None:
            for subparser in action.choices.values():
                if isinstance(subparser, ArgumentParser):
                    self._remap_container_destinations(subparser)

    def _extract_destination(self, *args: str, **kwargs: Any) -> str:
        if DEST_KEY in kwargs and kwargs[DEST_KEY] is not None:
            return kwargs[DEST_KEY]
        # Find first long option string, falling back to first short option
        option_strings = ((s, len(s) > 2) for s in args if s[0] in self.prefix_chars)
        for option_string, is_long in option_strings:
            if is_long and option_string[1] in self.prefix_chars:
                logger.debug(f"Using long option string for dest: {option_string}")
                return option_string.lstrip(self.prefix_chars)
        # If no long option found, use first short option
        dest = next(s.lstrip(self.prefix_chars) for s in args if s[0] in self.prefix_chars)
        logger.debug(f"Using short option string for dest: {dest}")
        return dest

    def _get_nested_destination(self, dest: str, *, store: bool = False) -> str:
        if not self.nest_path_components:
            return dest
        nested = f"{self.nest_separator.join(self.nest_path_components)}{self.nest_separator}{dest}"
        logger.info(f"Generated nested dest: {nested} -> {dest}")
        if store:
            self._original_destinations[nested] = dest
        return nested

    def _edit_arguments(self, original_dest: str, **kwargs: Any) -> dict[str, Any]:
        if kwargs.get("action", "store") == "store" and "metavar" not in kwargs:
            kwargs["metavar"] = original_dest.upper()
        return kwargs

    def _get_value(self, action: argparse.Action, arg_string: str) -> Any:
        parse_func = self._registry_get("type", action.type, action.type)
        if not callable(parse_func):
            raise argparse.ArgumentError(action, f"{parse_func!r} is not callable")
        try:
            result = parse_func(arg_string)

        except argparse.ArgumentTypeError:
            getattr(action.type, "__name__", repr(action.type))
            msg = str(sys.exc_info()[1])
            raise argparse.ArgumentError(action, msg)

        except (TypeError, ValueError):
            t = None
            if hasattr(parse_func, "keywords"):
                try:
                    t = parse_func.keywords.get("t")
                except Exception:
                    t = None
            if t is None:
                t = action.type if action.type is not None else "value"
            t_name = type_name(str(t))
            raise argparse.ArgumentError(action, f"invalid {t_name} value: '{arg_string}'")
        return result

    def error(self, message: str) -> None:
        """
        Override argparse's default error output for missing required subcommands.

        By default, argparse prints only a short usage line on errors. For CLIs built
        around subcommands, a missing subcommand is much more useful when the full help is displayed.
        """
        marker = "the following arguments are required:"
        if marker in message:
            subparser_dests: set[str] = {
                action.dest
                for action in self._actions
                if isinstance(action, argparse._SubParsersAction)
            }

            if subparser_dests:
                missing_part = message.split(marker, 1)[1].strip()
                missing_names = [name.strip() for name in missing_part.split(",") if name.strip()]
                denested_missing = [
                    self._original_destinations.get(name, name) for name in missing_names
                ]
                denested_subparser_dests = {
                    self._original_destinations.get(dest, dest) for dest in subparser_dests
                }

                if any(name in denested_subparser_dests for name in denested_missing):
                    denested_message = message
                    for nested, original in self._original_destinations.items():
                        denested_message = denested_message.replace(nested, original)

                    self._print_message(f"{self.prog}: error: {denested_message}\n", sys.stderr)
                    self.print_help(sys.stderr)
                    raise SystemExit(2)

        super().error(message)

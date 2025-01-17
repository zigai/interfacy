import argparse
import sys
from typing import Any, Callable, Literal, Sequence, Type

from objinspect.typing import type_name

from interfacy_cli.argparse_backend.help_formatter import InterfacyHelpFormatter

DEBUG = 0


def log(message: str, indent: int = 0):
    if DEBUG:
        print(f"{' '*indent}{message}")


DEST_KEY = "dest"
ActionType = Callable[[str], Any] | Type[Any] | str | None
NargsPattern = Literal["?", "*", "+"]


class NestedSubParsersAction(argparse._SubParsersAction):
    def __init__(
        self,
        option_strings: list[str],
        prog: str,
        base_nest_path: list[str],
        nest_separator: str,
        parser_class: Type["ArgumentParser"] | None = None,
        dest: str = argparse.SUPPRESS,
        required: bool = False,
        help: str | None = None,
        metavar: str | None = None,
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
        formatter_class: Type[argparse.HelpFormatter] = argparse.HelpFormatter,
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
        """Creates and returns a new parser for a subcommand with nesting support.

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
            add_help (bool, optional): Add -h/-help option. Defaults to True.
            allow_abbrev (bool, optional): Allow abbreviated long options. Defaults to True.
            exit_on_error (bool, optional): Exit with error info on error. Defaults to True.
            nest_dir (str | None, optional): Custom nesting directory name. Defaults to name if not provided.
            **kwargs: Additional arguments passed to parent class.

        Returns:
            NestedArgumentParser: A new parser for the subcommand.
        """
        return super().add_parser(
            name,
            help=help,
            aliases=aliases,
            prog=prog,
            usage=usage,
            description=description,
            epilog=epilog,
            parents=parents,
            formatter_class=formatter_class,
            prefix_chars=prefix_chars,
            fromfile_prefix_chars=fromfile_prefix_chars,
            argument_default=argument_default,
            conflict_handler=conflict_handler,
            add_help=add_help,
            allow_abbrev=allow_abbrev,
            nest_path=self.base_nest_path_components + [nest_dir or name],
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
        parents: list[argparse.ArgumentParser] = [],
        formatter_class: Type[argparse.HelpFormatter] = InterfacyHelpFormatter,
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
            add_help (bool, optional): Whether to add a -h/-help option.
            allow_abbrev (bool, optional): Whether to allow long options to be abbreviated unambiguously.
            exit_on_error (bool, optional): Whether ArgumentParser exits with error info when an error occurs.
        """

        self.nest_path_components = nest_path or ([nest_dir] if nest_dir else [])
        self.nest_dir = self.nest_path_components[-1] if self.nest_path_components else None
        self.nest_separator = nest_separator
        self._original_destinations: dict[str, str] = {}  # nested_dest: original_dest

        super().__init__(
            prog=prog,
            usage=usage,
            description=description,
            epilog=epilog,
            parents=parents,
            formatter_class=formatter_class,
            prefix_chars=prefix_chars,
            fromfile_prefix_chars=fromfile_prefix_chars,
            argument_default=argument_default,
            conflict_handler=conflict_handler,
            add_help=add_help,
            exit_on_error=exit_on_error,
            allow_abbrev=allow_abbrev,
        )
        self.register("action", "parsers", NestedSubParsersAction)

    def add_subparsers(self, **kwargs: Any) -> NestedSubParsersAction:
        log(f"Adding subparsers with kwargs={kwargs}")
        if DEST_KEY in kwargs:
            dest = kwargs[DEST_KEY]
            nested_dest = self._get_nested_destination(dest.replace("-", "_"), store=True)
            kwargs[DEST_KEY] = nested_dest

        kwargs.update(
            {"base_nest_path": self.nest_path_components, "nest_separator": self.nest_separator}
        )
        return super().add_subparsers(**kwargs)  # type: ignore

    def parse_known_args(  # type: ignore
        self,
        args: Sequence[str] | None = None,
        namespace: argparse.Namespace | None = None,
    ) -> tuple[argparse.Namespace, list[str]]:
        parsed_args, unknown_args = super().parse_known_args(args=args, namespace=namespace)
        log(f"initial parse result: parsed={vars(parsed_args)}, unknown={unknown_args}", indent=0)
        if parsed_args is None:
            raise ValueError("No parsed arguments found.")
        deflattened_args = self._deflatten_namespace(parsed_args)
        log(f"deflattened result: {vars(deflattened_args)}", indent=0)
        return deflattened_args, unknown_args

    def set_defaults(self, **kwargs: Any) -> None:
        nested_kwargs = {
            self._get_nested_destination(dest, store=True): value for dest, value in kwargs.items()
        }
        log(f"nested defaults: {nested_kwargs}")
        super().set_defaults(**nested_kwargs)

    def get_default(self, dest: str) -> Any:
        nested_dest = self._get_nested_destination(dest)
        value = super().get_default(nested_dest)
        return value

    def _add_container_actions(self, container: argparse._ActionsContainer) -> None:
        self._remap_container_destinations(container)
        return super()._add_container_actions(container)

    def _get_positional_kwargs(self, dest: str, **kwargs: Any) -> dict[str, Any]:
        log(f"getting positional kwargs for dest={dest} {kwargs}", indent=2)
        nested_dest = self._get_nested_destination(dest.replace("-", "_"), store=True)
        kwargs = self._edit_arguments(dest, **kwargs)
        return super()._get_positional_kwargs(nested_dest, **kwargs)

    def _get_optional_kwargs(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        log(f"getting optional kwargs for args={args}: {kwargs}", indent=2)
        dest = self._extract_destination(*args, **kwargs)
        nested_dest = self._get_nested_destination(dest.replace("-", "_"), store=True)
        kwargs[DEST_KEY] = nested_dest
        kwargs = self._edit_arguments(dest, **kwargs)
        return super()._get_optional_kwargs(*args, **kwargs)

    def _deflatten_namespace(self, namespace: argparse.Namespace) -> argparse.Namespace:
        log(f"starting namespace deflattening for: {vars(namespace)}", indent=2)
        root = argparse.Namespace()

        for key, value in vars(namespace).items():
            components = key.split(self.nest_separator)
            current = root

            # Navigate through component hierarchy
            for component in components[:-1]:
                if not hasattr(current, component):
                    log(f"creating new namespace for component: {component}", indent=6)
                    setattr(current, component, argparse.Namespace())
                current = getattr(current, component)

            # Set or merge final value
            final_component = components[-1]
            if hasattr(current, final_component):
                log(f"Handling conflict at {final_component}", indent=6)
                existing_value = getattr(current, final_component)
                if isinstance(existing_value, argparse.Namespace) and isinstance(
                    value, argparse.Namespace
                ):
                    self._recursively_merge_namespaces(existing_value, value)
                else:
                    raise ValueError(f'Cannot merge namespaces due to conflict at key "{key}"')
            else:
                setattr(current, final_component, value)

        return root

    def _recursively_merge_namespaces(
        self, destination: argparse.Namespace, source: argparse.Namespace
    ) -> argparse.Namespace:
        for name, value in vars(source).items():
            if hasattr(destination, name):
                dest_value = getattr(destination, name)
                if isinstance(dest_value, argparse.Namespace) and isinstance(
                    value, argparse.Namespace
                ):
                    log(f"recursively merging at attribute: {name}")
                    self._recursively_merge_namespaces(dest_value, value)
                else:
                    raise ValueError(
                        f'Cannot merge namespaces due to conflict at attribute "{name}".'
                    )
            else:
                log(f"setting new attribute: {name}={value}")
                setattr(destination, name, value)
        return destination

    def _remap_container_destinations(self, container: argparse._ActionsContainer) -> None:
        log(f"remapping container destinations: {container._defaults}")
        container._defaults = {
            self._get_nested_destination(dest): value for dest, value in container._defaults.items()
        }
        log(f"remapped container destinations: {container._defaults}")

        for action in container._actions:
            self._remap_action_destinations(action)

    def _remap_action_destinations(self, action: argparse.Action) -> None:
        log(f"remapping action: {action}")

        if action.dest is not None:
            old_dest = action.dest
            action.dest = self._get_nested_destination(action.dest, store=True)
            log(f"remapped action dest from {old_dest} to {action.dest}")

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
                log(f"using long option string for dest: {option_string}")
                return option_string.lstrip(self.prefix_chars)
        # If no long option found, use first short option
        dest = next(s.lstrip(self.prefix_chars) for s in args if s[0] in self.prefix_chars)
        log(f"using short option string for dest: {dest}")
        return dest

    def _get_nested_destination(self, dest: str, *, store: bool = False) -> str:
        if not self.nest_path_components:
            return dest
        nested = f"{self.nest_separator.join(self.nest_path_components)}{self.nest_separator}{dest}"
        log(f"generated nested dest: {nested} -> {dest}")
        if store:
            self._original_destinations[nested] = dest
        return nested

    def _edit_arguments(self, original_dest: str, **kwargs: Any) -> dict[str, Any]:
        if kwargs.get("action", "store") == "store" and "metavar" not in kwargs:
            kwargs["metavar"] = original_dest.upper()
        return kwargs

    def _get_value(self, action, arg_string):
        parse_func = self._registry_get("type", action.type, action.type)
        if not callable(parse_func):
            msg = _("%r is not callable")
            raise argparse.ArgumentError(action, msg % parse_func)
        try:
            result = parse_func(arg_string)

        except argparse.ArgumentTypeError:
            name = getattr(action.type, "__name__", repr(action.type))
            msg = str(sys.exc_info()[1])
            raise argparse.ArgumentError(action, msg)

        except (TypeError, ValueError):
            t = type_name(str(parse_func.keywords["t"]))
            raise argparse.ArgumentError(action, f"invalid {t} value: '{arg_string}'")
        return result

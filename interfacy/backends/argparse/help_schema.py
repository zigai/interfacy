from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence

from interfacy.declarations.params import BooleanMode
from interfacy.schema.model import (
    Argument,
    ArgumentDefault,
    ArgumentKind,
    BooleanBehavior,
    Command,
    ValueShape,
)
from interfacy.schema.values import ValueCardinality

ChildCommandBuilder = Callable[[argparse.ArgumentParser], Command | None]


def action_to_help_argument(action: argparse.Action) -> Argument:
    """
    Convert an argparse help action into a schema help argument.

    Args:
        action (argparse.Action): The parser's help action.
    """
    help_text = action.help if isinstance(action.help, str) else None
    return Argument(
        name=action.dest or "help",
        display_name=action.dest or "help",
        kind=ArgumentKind.OPTION,
        value_shape=ValueShape.FLAG,
        flags=tuple(action.option_strings),
        required=False,
        cardinality=ValueCardinality(0, 0, 0),
        argument_default=ArgumentDefault.present(
            action.default,
            suppress_help_default=True,
        ),
        help=help_text,
        type=None,
        parser=None,
        is_help_action=True,
    )


def help_argument_from_actions(actions: Sequence[argparse.Action]) -> Argument | None:
    """
    Return the schema help argument for the first argparse help action, if any.

    Args:
        actions (Sequence[argparse.Action]): Actions registered on a parser.
    """
    for action in actions:
        if isinstance(action, argparse._HelpAction):  # type: ignore[private-member-access]
            return action_to_help_argument(action)

    return None


def action_metavar(action: argparse.Action) -> str | None:
    """
    Return an action's metavar when it is a plain string.

    Args:
        action (argparse.Action): Action to inspect.
    """
    metavar = action.metavar
    return metavar if isinstance(metavar, str) else None


def action_value_shape(action: argparse.Action) -> ValueShape:
    """
    Infer the schema value shape of an argparse action.

    Args:
        action (argparse.Action): Action to inspect.
    """
    if getattr(action, "nargs", None) == 0:
        return ValueShape.FLAG
    if isinstance(action, argparse._AppendAction):  # type: ignore[private-member-access]
        return ValueShape.LIST
    if isinstance(action.nargs, int) and action.nargs > 1:
        return ValueShape.TUPLE
    if action.nargs in ("*", "+"):
        return ValueShape.LIST

    return ValueShape.SINGLE


def action_cardinality(action: argparse.Action) -> ValueCardinality:
    """
    Infer the schema value cardinality of an argparse action.

    Args:
        action (argparse.Action): Action to inspect.
    """
    nargs = action.nargs
    if nargs == 0:
        return ValueCardinality(0, 0, 0)
    if nargs == "?":
        return ValueCardinality(0, 1, 1)
    if nargs == "*":
        return ValueCardinality(0, None, 1)
    if nargs == "+":
        return ValueCardinality(1, None, 1)
    if isinstance(nargs, int):
        return ValueCardinality(nargs, nargs, nargs)
    return ValueCardinality(1, 1, 1)


def boolean_behavior_from_action(action: argparse.Action) -> BooleanBehavior:
    """
    Describe the boolean flags of a zero-argument option action.

    Args:
        action (argparse.Action): Flag action with option strings.
    """
    option_strings = tuple(action.option_strings)
    if isinstance(action, argparse._StoreFalseAction):  # type: ignore[private-member-access]
        positive_flags: tuple[str, ...] = ()
        negative_flags = option_strings
    elif isinstance(action, argparse.BooleanOptionalAction):
        negative_flags = tuple(flag for flag in option_strings if flag.startswith("--no-"))
        positive_flags = tuple(flag for flag in option_strings if flag not in negative_flags)
    else:
        positive_flags = option_strings
        negative_flags = ()

    if positive_flags and negative_flags:
        mode = BooleanMode.DUAL
    elif negative_flags:
        mode = BooleanMode.NEGATIVE_ONLY
    else:
        mode = BooleanMode.POSITIVE_ONLY

    return BooleanBehavior(
        positive_flags=positive_flags,
        negative_flags=negative_flags,
        default=action.default,
        mode=mode,
    )


def argument_from_action(action: argparse.Action, dest_name: str) -> Argument:
    """
    Convert a manually added argparse action into a schema argument.

    Args:
        action (argparse.Action): Action to convert.
        dest_name (str): Original (non-nested) destination name of the action.
    """
    value_shape = action_value_shape(action)
    display_name = dest_name.replace("_", "-")
    kind = ArgumentKind.OPTION if action.option_strings else ArgumentKind.POSITIONAL

    arg_type = action.type if isinstance(action.type, type) else None
    parser = action.type if callable(action.type) else None

    if arg_type is None and value_shape != ValueShape.FLAG:
        arg_type = str

    boolean_behavior: BooleanBehavior | None = None
    if value_shape == ValueShape.FLAG and action.option_strings:
        boolean_behavior = boolean_behavior_from_action(action)

    choices = tuple(action.choices) if action.choices is not None else None
    argument_default = (
        ArgumentDefault.absent()
        if action.default is argparse.SUPPRESS
        else ArgumentDefault.present(action.default)
    )

    return Argument(
        name=dest_name,
        display_name=display_name,
        kind=kind,
        value_shape=value_shape,
        flags=tuple(action.option_strings) if action.option_strings else (display_name,),
        required=bool(getattr(action, "required", False)),
        cardinality=action_cardinality(action),
        argument_default=argument_default,
        help=action.help if isinstance(action.help, str) else None,
        type=arg_type,
        parser=parser,
        metavar=action_metavar(action),
        boolean_behavior=boolean_behavior,
        choices=choices,
    )


def subcommands_from_action(
    action: argparse._SubParsersAction,  # type: ignore[private-member-access]
    child_command: ChildCommandBuilder,
) -> dict[str, Command] | None:
    """
    Convert an argparse subparsers action into schema subcommands.

    Args:
        action (argparse._SubParsersAction): Subparsers action to convert.
        child_command (ChildCommandBuilder): Builds the implicit command for a child
            parser, or returns None to skip parsers it does not understand.
    """
    parser_names: dict[int, list[str]] = {}
    for name, parser in action.choices.items():
        parser_names.setdefault(id(parser), []).append(name)

    commands: dict[str, Command] = {}

    for choice_action in getattr(action, "_choices_actions", ()):
        choice_name = getattr(choice_action, "dest", None)
        if not isinstance(choice_name, str):
            continue

        parser = action.choices.get(choice_name)
        if parser is None:
            continue

        implicit = child_command(parser)
        if implicit is None:
            continue

        aliases = tuple(name for name in parser_names.get(id(parser), ()) if name != choice_name)
        raw_description = (
            choice_action.help
            if isinstance(choice_action.help, str) and choice_action.help != argparse.SUPPRESS
            else parser.description
        )
        commands[choice_name] = Command(
            obj=None,
            canonical_name=choice_name,
            cli_name=choice_name,
            aliases=aliases,
            raw_description=raw_description,
            parameters=implicit.parameters,
            subcommands=implicit.subcommands,
            raw_epilog=parser.epilog,
            is_leaf=not bool(implicit.subcommands),
        )

    return commands or None


def command_name_for_prog(prog: str | None) -> str:
    """
    Derive a schema command name from a parser's ``prog``.

    Args:
        prog (str | None): Program string of the parser.
    """
    stripped = (prog or "command").strip()
    if not stripped:
        return "command"

    return stripped.split()[-1]


def implicit_command(
    actions: Sequence[argparse.Action],
    *,
    prog: str | None,
    description: str | None,
    epilog: str | None,
    dest_name: Callable[[str], str],
    child_command: ChildCommandBuilder,
) -> Command:
    """
    Synthesize a schema command from a manually built argparse parser.

    Args:
        actions (Sequence[argparse.Action]): Actions registered on the parser.
        prog (str | None): Program string of the parser.
        description (str | None): Parser description.
        epilog (str | None): Parser epilog.
        dest_name (Callable[[str], str]): Resolves an action destination to its original name.
        child_command (ChildCommandBuilder): Builds implicit commands for child parsers.
    """
    parameters: list[Argument] = []
    subcommands: dict[str, Command] | None = None

    for action in actions:
        if isinstance(action, argparse._HelpAction):  # type: ignore[private-member-access]
            continue

        if isinstance(action, argparse._SubParsersAction):  # type: ignore[private-member-access]
            subcommands = subcommands_from_action(action, child_command)
            continue

        parameters.append(argument_from_action(action, dest_name(action.dest)))

    command_name = command_name_for_prog(prog)

    return Command(
        obj=None,
        canonical_name=command_name,
        cli_name=command_name,
        aliases=(),
        raw_description=description,
        parameters=parameters,
        subcommands=subcommands,
        raw_epilog=epilog,
        is_leaf=not bool(subcommands),
    )


__all__ = [
    "ChildCommandBuilder",
    "action_cardinality",
    "action_metavar",
    "action_to_help_argument",
    "action_value_shape",
    "argument_from_action",
    "boolean_behavior_from_action",
    "command_name_for_prog",
    "help_argument_from_actions",
    "implicit_command",
    "subcommands_from_action",
]

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from interfacy.schema.schema import Argument, Command, ParserSchema


class InterspersedOptionValueError(ValueError):
    """Raised when a normalized interspersed option value fails conversion."""

    def __init__(
        self,
        argument: Argument,
        raw_value: str,
        original: TypeError | ValueError,
    ) -> None:
        self.argument = argument
        self.raw_value = raw_value
        self.original = original
        super().__init__(str(original))


class AncestorOptions:
    """Normalize late ancestor options and carry values that backends cannot parse directly."""

    def __init__(self) -> None:
        self._pending_values: list[tuple[tuple[str, ...], Argument, tuple[str, ...]]] = []

    def normalize_args(
        self,
        schema: ParserSchema,
        args: Sequence[str],
    ) -> list[str]:
        self._pending_values = []
        normalized_args = list(args)
        if not normalized_args:
            return normalized_args

        implicit_command = self._single_command_without_root_selection(schema)
        command_chain = [implicit_command] if implicit_command else []
        command_token_positions: list[int | None] = [None] if implicit_command else []
        insertions: dict[int, list[list[str]]] = {}
        removed_indexes: set[int] = set()

        index = 0
        while index < len(normalized_args):
            arg = normalized_args[index]
            if arg == "--":
                break

            option_end = self._queue_late_ancestor_option(
                schema,
                normalized_args,
                index,
                command_chain,
                command_token_positions,
                insertions,
                removed_indexes,
            )
            if option_end is not None:
                index = option_end
                continue

            self._append_matching_command(
                schema,
                arg,
                command_chain,
                command_token_positions,
                index,
            )

            index += 1

        if not insertions and not removed_indexes:
            return normalized_args

        reordered: list[str] = []
        for index, token in enumerate(normalized_args):
            for group in insertions.get(index, []):
                reordered.extend(group)

            if index not in removed_indexes:
                reordered.append(token)

        for group in insertions.get(len(normalized_args), []):
            reordered.extend(group)

        return reordered

    def apply_values(
        self,
        schema: ParserSchema,
        namespace: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            for command_path, argument, raw_values in self._pending_values:
                value = self._parse_option_values(argument, raw_values)
                bucket = self._bucket_for_command_path(schema, namespace, command_path, create=True)
                if bucket is not None:
                    bucket[argument.name] = value
        finally:
            self._pending_values = []

        return namespace

    @staticmethod
    def _single_command_without_root_selection(schema: ParserSchema) -> Command | None:
        if len(schema.commands) != 1:
            return None

        command = next(iter(schema.commands.values()))
        if command.command_type == "group":
            return None

        return command

    @staticmethod
    def _match_command_name(
        commands: Mapping[str, Command],
        cli_name: str,
    ) -> Command | None:
        for command in commands.values():
            if command.cli_name == cli_name or cli_name in command.aliases:
                return command

        return None

    @staticmethod
    def _argument_option_flags(argument: Argument) -> tuple[str, ...]:
        boolean_behavior = argument.boolean_behavior
        if boolean_behavior is not None:
            return (*boolean_behavior.positive_flags, *boolean_behavior.negative_flags)

        return argument.flags

    def _match_option_argument(
        self,
        token: str,
        command: Command,
    ) -> Argument | None:
        if token in ("", "-", "--") or not token.startswith("-"):
            return None

        option_token = token.split("=", 1)[0] if token.startswith("--") else token
        arguments = [*command.initializer, *command.parameters]
        for argument in arguments:
            flags = self._argument_option_flags(argument)
            if option_token in flags:
                return argument

        if token.startswith("--"):
            matches = [
                argument
                for argument in arguments
                for flag in self._argument_option_flags(argument)
                if flag.startswith("--") and flag.startswith(option_token)
            ]
            unique_matches = {id(argument): argument for argument in matches}
            if len(unique_matches) == 1:
                return next(iter(unique_matches.values()))

            return None

        if len(token) > 2:
            short_flag = token[:2]
            for argument in arguments:
                if short_flag in self._argument_option_flags(argument):
                    return argument

        return None

    def _find_nearest_option_owner(
        self,
        token: str,
        command_chain: Sequence[Command],
    ) -> tuple[int, Argument] | None:
        for index in range(len(command_chain) - 1, -1, -1):
            argument = self._match_option_argument(token, command_chain[index])
            if argument is not None:
                return index, argument

        return None

    def _option_group_end(
        self,
        args: Sequence[str],
        start: int,
        argument: Argument,
        command_chain: Sequence[Command],
    ) -> int:
        token = args[start]
        if token.startswith("--") and "=" in token:
            return start + 1
        if argument.boolean_behavior is not None:
            return start + 1
        if token.startswith("-") and not token.startswith("--") and len(token) > 2:
            return start + 1

        cardinality = argument.cardinality
        if cardinality.maximum_values is not None:
            return min(len(args), start + 1 + cardinality.maximum_values)

        if cardinality.maximum_values is None:
            index = start + 1
            while index < len(args):
                value = args[index]
                if value == "--" or self._find_nearest_option_owner(value, command_chain):
                    break

                if (
                    command_chain
                    and command_chain[-1].subcommands
                    and self._match_command_name(command_chain[-1].subcommands, value)
                ):
                    break

                index += 1

            return index

        return min(len(args), start + 2)

    @staticmethod
    def _option_group_raw_values(
        args: Sequence[str],
        start: int,
        end: int,
        argument: Argument,
    ) -> list[str]:
        token = args[start]
        if token.startswith("--") and "=" in token:
            return [token.split("=", 1)[1]]
        if token.startswith("-") and not token.startswith("--") and len(token) > 2:
            return [token[2:]]
        if argument.boolean_behavior is not None:
            return []

        return list(args[start + 1 : end])

    @staticmethod
    def _parse_option_values(argument: Argument, raw_values: Sequence[str]) -> Any:
        parse = argument.parser
        values: list[Any] = []
        for raw_value in raw_values:
            try:
                value = parse(raw_value) if parse is not None else raw_value
            except (TypeError, ValueError) as exc:
                raise InterspersedOptionValueError(argument, raw_value, exc) from exc

            values.append(value)

        if argument.value_shape.name == "LIST":
            return values
        if argument.value_shape.name == "TUPLE":
            return tuple(values)

        return values[-1] if values else None

    def _command_path_for_option_owner(
        self,
        schema: ParserSchema,
        command_chain: Sequence[Command],
        owner_index: int,
    ) -> tuple[str, ...]:
        root_command = self._single_command_without_root_selection(schema)
        start = 1 if command_chain and command_chain[0] is root_command else 0
        return tuple(command.cli_name for command in command_chain[start : owner_index + 1])

    @staticmethod
    def _ancestor_option_insertion_index(
        owner_index: int,
        command_token_positions: Sequence[int | None],
    ) -> int:
        if owner_index + 1 < len(command_token_positions):
            child_position = command_token_positions[owner_index + 1]
            if child_position is not None:
                return child_position

        owner_position = command_token_positions[owner_index]
        if owner_position is None:
            return 0

        return owner_position + 1

    def _queue_late_ancestor_option(
        self,
        schema: ParserSchema,
        args: Sequence[str],
        index: int,
        command_chain: Sequence[Command],
        command_token_positions: Sequence[int | None],
        insertions: dict[int, list[list[str]]],
        removed_indexes: set[int],
    ) -> int | None:
        owner = self._find_nearest_option_owner(args[index], command_chain)
        if owner is None:
            return None

        owner_index, argument = owner
        end = self._option_group_end(args, index, argument, command_chain)
        if owner_index >= len(command_chain) - 1:
            return end

        insertion_index = self._ancestor_option_insertion_index(
            owner_index,
            command_token_positions,
        )
        if insertion_index < index:
            option_group = list(args[index:end])
            if argument.value_shape.name == "LIST":
                raw_values = self._option_group_raw_values(args, index, end, argument)
                option_group = []
                command_path = self._command_path_for_option_owner(
                    schema,
                    command_chain,
                    owner_index,
                )
                self._pending_values.append((command_path, argument, tuple(raw_values)))

            if option_group:
                insertions.setdefault(insertion_index, []).append(option_group)

            removed_indexes.update(range(index, end))

        return end

    def _append_matching_command(
        self,
        schema: ParserSchema,
        arg: str,
        command_chain: list[Command],
        command_token_positions: list[int | None],
        index: int,
    ) -> None:
        available_commands = command_chain[-1].subcommands if command_chain else schema.commands
        if not available_commands:
            return

        command = self._match_command_name(available_commands, arg)
        if command is None:
            return

        command_chain.append(command)
        command_token_positions.append(index)

    def _bucket_for_command_path(
        self,
        schema: ParserSchema,
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


__all__ = ["AncestorOptions", "InterspersedOptionValueError"]

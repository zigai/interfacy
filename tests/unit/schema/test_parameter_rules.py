from collections.abc import Callable
from typing import Annotated

import pytest

from interfacy import Interfacy, Param, params
from interfacy.exceptions import ReservedFlagError
from interfacy.naming import DefaultFlagStrategy


def reserved(help: int) -> None:
    return None


class NeedsCommandKey:
    def __init__(self, command: int) -> None:
        self.command = command

    def run(self) -> None: ...


def test_reserved_flag_name_raises() -> None:
    """Verify that a parameter colliding with the help flag is rejected."""
    parser = Interfacy()
    parser.add_command(reserved)

    with pytest.raises(ReservedFlagError, match="help"):
        parser.build_parser_schema()


def test_command_key_collision_raises() -> None:
    """Verify that an initializer parameter named like the command key is rejected."""
    parser = Interfacy()
    parser.add_command(NeedsCommandKey)

    with pytest.raises(ReservedFlagError):
        parser.build_parser_schema()


def test_optional_list_default_is_fresh_for_each_invocation() -> None:
    """Verify that mutating a generated empty list default does not leak into later runs."""

    def collect(values: list[int] | None) -> list[int] | None:
        assert values is not None
        values.append(1)

        return values

    parser = Interfacy()
    parser.add_command(collect)

    assert parser.invoke(args=[]) == [1]
    assert parser.invoke(args=[]) == [1]


def test_untyped_parameter_receives_raw_string() -> None:
    """Verify that untyped parameters receive the CLI token unchanged."""

    def untyped(value):
        return value

    assert Interfacy().invoke(untyped, args=["7"]) == "7"


def test_callable_and_annotated_unhashable_metadata_do_not_crash() -> None:
    """Verify Callable and Annotated with unhashable metadata do not crash schema building."""

    def cmd(
        callback: Callable[[int], int],
        unhashable: Annotated[int, [1, 2]],
        param: Annotated[int, Param(kind="option")],
    ) -> None:
        pass

    parser = Interfacy()
    parser.add_command(cmd)

    assert len(parser.build_parser_schema().commands["cmd"].arguments) == 3


@params(alpha=Param(short=False), amount=Param(short=False), active=Param(short=False))
def fn_long_only_flags(
    alpha: bool = False,
    amount: bool = False,
    active: bool = False,
    archive: str = "default",
) -> tuple[str, bool, bool, bool]:
    return archive, alpha, amount, active


def fn_custom_output_format(output_format: str = "text") -> str:
    return output_format


def test_param_short_false_keeps_later_short_flags_available() -> None:
    parser = Interfacy(
        backend="argparse",
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        help_layout=None,
    )
    parser.add_command(fn_long_only_flags)

    schema = parser.build_parser_schema()
    command = schema.commands["fn-long-only-flags"]
    flags = {argument.name: argument.flags for argument in command.arguments}

    assert flags["alpha"] == ("--alpha",)
    assert flags["amount"] == ("--amount",)
    assert flags["active"] == ("--active",)
    assert flags["archive"] == ("-a", "--archive")


def test_param_can_override_help_and_metavar() -> None:
    parser = Interfacy(
        backend="argparse",
        flag_strategy=DefaultFlagStrategy(style="required_positional"),
        help_layout=None,
    )
    parser.add_command(
        fn_custom_output_format,
        params={
            "output_format": Param(help="Output rendering format.", metavar="FORMAT"),
        },
    )

    argument = parser.build_parser_schema().commands["fn-custom-output-format"].arguments[0]

    assert argument.help == "Output rendering format."
    assert argument.metavar == "FORMAT"

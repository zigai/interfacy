from __future__ import annotations

from interfacy import Interfacy, Param


def test_positional_parameter_named_underscore() -> None:
    """Verify positional parameter named '_' does not crash with IndexError."""

    def dummy(_: int) -> int:
        return _

    cli = Interfacy()
    cli.add_command(dummy)
    assert cli.invoke(args=["42"]) == 42


def test_single_letter_parameter_short_and_long_flags() -> None:
    """Verify single-letter parameter accepting both short and long flag does not collide with itself."""

    def configure(c: int = 1) -> int:
        return c

    cli = Interfacy()
    cli.add_command(configure, parameter_settings={"c": Param(flags=["-c", "--c"])})

    assert cli.invoke(args=["-c", "10"]) == 10
    assert cli.invoke(args=["--c", "20"]) == 20

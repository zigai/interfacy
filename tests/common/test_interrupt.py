"""Tests for KeyboardInterrupt (Ctrl+C) signal handling."""

import signal
import threading
import time

import pytest

from interfacy import Argparser
from interfacy.core import ExitCode


def slow_task(seconds: int = 10) -> str:
    """A slow task that can be interrupted."""
    for i in range(seconds):
        time.sleep(0.1)
    return "Done"


def immediate_task() -> str:
    """A task that completes immediately."""
    return "Done"


class TestInterruptExitCode:
    """Test that KeyboardInterrupt results in exit code 130."""

    def test_exit_code_value(self):
        """Verify INTERRUPTED exit code is 130 (Unix convention)."""
        assert ExitCode.INTERRUPTED == 130

    def test_interrupt_returns_keyboard_interrupt(self):
        """Verify run() returns KeyboardInterrupt on interrupt."""
        parser = Argparser(sys_exit_enabled=False)

        def raises_interrupt() -> None:
            raise KeyboardInterrupt()

        result = parser.run(raises_interrupt, args=[])
        assert isinstance(result, KeyboardInterrupt)


class TestInterruptCallback:
    """Test the on_interrupt callback functionality."""

    def test_callback_is_invoked(self):
        """Verify on_interrupt callback is called on interrupt."""
        callback_called = []

        def my_callback(exc: KeyboardInterrupt) -> None:
            callback_called.append(exc)

        parser = Argparser(sys_exit_enabled=False, on_interrupt=my_callback)

        def raises_interrupt() -> None:
            raise KeyboardInterrupt()

        parser.run(raises_interrupt, args=[])
        assert len(callback_called) == 1
        assert isinstance(callback_called[0], KeyboardInterrupt)

    def test_callback_not_called_on_success(self):
        """Verify on_interrupt callback is NOT called on successful completion."""
        callback_called = []

        def my_callback(exc: KeyboardInterrupt) -> None:
            callback_called.append(exc)

        parser = Argparser(sys_exit_enabled=False, on_interrupt=my_callback)
        result = parser.run(immediate_task, args=[])
        assert result == "Done"
        assert len(callback_called) == 0


class TestSilentInterrupt:
    """Test the silent_interrupt flag."""

    def test_silent_interrupt_suppresses_message(self, capsys):
        """Verify silent_interrupt=True suppresses the interrupt message."""
        parser = Argparser(sys_exit_enabled=False, silent_interrupt=True)

        def raises_interrupt() -> None:
            raise KeyboardInterrupt()

        parser.run(raises_interrupt, args=[])
        captured = capsys.readouterr()
        assert "Interrupted" not in captured.err

    def test_non_silent_interrupt_shows_message(self, capsys):
        """Verify silent_interrupt=False (default) shows the interrupt message."""
        parser = Argparser(sys_exit_enabled=False, silent_interrupt=False)

        def raises_interrupt() -> None:
            raise KeyboardInterrupt()

        parser.run(raises_interrupt, args=[])
        captured = capsys.readouterr()
        assert "Interrupted" in captured.err


class TestReraiseInterrupt:
    """Test the reraise_interrupt flag."""

    def test_reraise_interrupt_raises_after_handling(self):
        """Verify reraise_interrupt=True re-raises KeyboardInterrupt after handling."""
        parser = Argparser(sys_exit_enabled=False, reraise_interrupt=True)

        def raises_interrupt() -> None:
            raise KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            parser.run(raises_interrupt, args=[])

    def test_no_reraise_by_default(self):
        """Verify reraise_interrupt=False (default) does not re-raise."""
        parser = Argparser(sys_exit_enabled=False, reraise_interrupt=False)

        def raises_interrupt() -> None:
            raise KeyboardInterrupt()

        # Should not raise, just return the exception
        result = parser.run(raises_interrupt, args=[])
        assert isinstance(result, KeyboardInterrupt)


class TestInterruptDuringParsing:
    """Test interrupt handling during argument parsing phase."""

    def test_interrupt_during_command_setup(self):
        """Verify interrupt during command setup is handled gracefully."""
        callback_called = []

        def my_callback(exc: KeyboardInterrupt) -> None:
            callback_called.append(True)

        parser = Argparser(sys_exit_enabled=False, on_interrupt=my_callback)

        class InterruptingCommand:
            def __init__(self) -> None:
                raise KeyboardInterrupt()

            def action(self) -> None:
                pass

        result = parser.run(InterruptingCommand, args=["action"])
        assert isinstance(result, KeyboardInterrupt) or len(callback_called) > 0

from __future__ import annotations

import asyncio

import pytest

from interfacy import Interfacy
from interfacy.runtime.exit_codes import ExitCode


def test_async_cancelled_error_exits_with_interrupted() -> None:
    """Verify asyncio.CancelledError inside an async command cleanly exits with ExitCode.INTERRUPTED."""

    async def cancelled_cmd() -> None:
        task = asyncio.current_task()
        if task is not None:
            task.cancel()

        await asyncio.sleep(0.1)

    cli = Interfacy(sys_exit_enabled=True)
    cli.add_command(cancelled_cmd)

    with pytest.raises(SystemExit) as exc_info:
        cli.run(args=[])

    assert exc_info.value.code == ExitCode.INTERRUPTED


def test_print_result_with_sys_exit_disabled(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify print_result=True displays output when sys_exit_enabled=False."""

    def calc() -> int:
        return 42

    cli = Interfacy(print_result=True, sys_exit_enabled=False)
    cli.add_command(calc)

    res = cli.run(args=[])
    assert res == 42

    captured = capsys.readouterr()
    assert "42" in captured.out

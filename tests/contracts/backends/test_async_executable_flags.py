import asyncio
import inspect
from typing import Literal

import pytest

from interfacy import ExecutableFlag, ExitCode, Interfacy
from interfacy.engine.backend import ExecutableAction, ParseRequest
from interfacy.exceptions import ConfigurationError, InterfacyExit, UsageError
from interfacy.runtime.invocation import InvocationError


@pytest.fixture(params=["argparse", "click"])
def parser(request: pytest.FixtureRequest) -> Interfacy:
    if request.param == "click":
        pytest.importorskip("click")
    parser = Interfacy(backend=request.param)

    def required_command(value: str) -> str:
        pytest.fail("The executable flag must short-circuit command execution")

    parser.add_command(required_command)

    return parser


def test_backend_returns_action_without_running_flag_handler(parser: Interfacy, capsys) -> None:
    calls: list[str] = []
    flag = ExecutableFlag("--flag", lambda: calls.append("called"))
    parser.apply_setup(executable_flags=[flag])

    outcome = parser._engine._session().parse(ParseRequest(("--flag",)))

    assert isinstance(outcome, ExecutableAction)
    assert outcome.flag is flag
    assert calls == []
    assert capsys.readouterr().out == ""


def test_invoke_async_awaits_current_loop_future_once(parser: Interfacy, capsys) -> None:
    calls: list[str] = []

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        future = loop.create_future()

        def handler() -> asyncio.Future[str]:
            calls.append("handler")
            loop.call_soon(future.set_result, "future result")

            return future

        parser.apply_setup(executable_flags=[ExecutableFlag("--flag", handler)])

        assert await parser.invoke_async(args=["--flag"]) is None
        assert future.result() == "future result"

    asyncio.run(scenario())

    assert calls == ["handler"]
    assert capsys.readouterr().out == "future result\n"


def test_async_flag_uses_the_invoking_loop_for_its_resources(parser: Interfacy, capsys) -> None:
    calls: list[str] = []

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        ready = loop.create_future()

        async def handler() -> str:
            calls.append("handler")
            assert asyncio.get_running_loop() is loop
            loop.call_soon(ready.set_result, "ready")

            return await ready

        parser.apply_setup(executable_flags=[ExecutableFlag("--flag", handler)])

        assert await parser.invoke_async(args=["--flag"]) is None

    asyncio.run(scenario())

    assert calls == ["handler"]
    assert capsys.readouterr().out == "ready\n"


def test_async_flag_cancellation_propagates_and_cleans_up(parser: Interfacy, capsys) -> None:
    events: list[str] = []

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        started = asyncio.Event()
        release = asyncio.Event()

        async def handler() -> str:
            events.append("started")
            started.set()
            assert asyncio.get_running_loop() is loop
            try:
                await release.wait()
                return "unexpected"
            finally:
                events.append("cleaned up")

        parser.apply_setup(executable_flags=[ExecutableFlag("--flag", handler)])
        invocation = asyncio.create_task(parser.invoke_async(args=["--flag"]))
        await started.wait()
        invocation.cancel()

        with pytest.raises(asyncio.CancelledError):
            await invocation

    asyncio.run(scenario())

    assert events == ["started", "cleaned up"]
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("api", ["invoke", "parse_args"])
def test_sync_live_loop_rejection_closes_returned_coroutine(
    parser: Interfacy,
    api: Literal["invoke", "parse_args"],
    capsys,
) -> None:
    created = []

    async def handler_result() -> str:
        pytest.fail("Rejected synchronous invocations must not start the coroutine")

    def handler():
        result = handler_result()
        created.append(result)
        return result

    parser.apply_setup(executable_flags=[ExecutableFlag("--flag", handler)])

    async def scenario() -> None:
        if api == "invoke":
            with pytest.raises(RuntimeError, match="invoke_async"):
                parser.invoke(args=["--flag"])
        else:
            with pytest.raises(RuntimeError, match="invoke_async"):
                parser.parse_args(["--flag"])

    asyncio.run(scenario())

    assert len(created) == 1
    assert inspect.getcoroutinestate(created[0]) == inspect.CORO_CLOSED
    assert capsys.readouterr().out == ""


def test_sync_live_loop_rejection_does_not_cancel_callers_future(parser: Interfacy, capsys) -> None:
    async def scenario() -> None:
        future = asyncio.get_running_loop().create_future()
        parser.apply_setup(executable_flags=[ExecutableFlag("--flag", lambda: future)])

        with pytest.raises(RuntimeError, match="invoke_async"):
            parser.invoke(args=["--flag"])

        assert not future.done()
        future.set_result("still owned by caller")
        assert await future == "still owned by caller"

    asyncio.run(scenario())

    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("api", ["invoke", "parse_args", "run"])
def test_async_flag_outside_loop_preserves_sync_entry_points(
    parser: Interfacy,
    api: Literal["invoke", "parse_args", "run"],
    capsys,
) -> None:
    calls: list[str] = []

    async def handler() -> str:
        calls.append("handler")
        return "done"

    parser.apply_setup(executable_flags=[ExecutableFlag("--flag", handler, exit_code=7)])

    if api == "invoke":
        assert parser.invoke(args=["--flag"]) is None
    elif api == "parse_args":
        with pytest.raises(InterfacyExit) as e:
            parser.parse_args(["--flag"])

        assert e.value.code == 7
    else:
        with pytest.raises(SystemExit) as e:
            parser.run(args=["--flag"])

        assert e.value.code == 7

    assert calls == ["handler"]
    assert capsys.readouterr().out == "done\n"


def test_invoke_async_accepts_sync_flag_and_honors_display_toggle(
    parser: Interfacy, capsys
) -> None:
    calls: list[str] = []

    def handler() -> str:
        calls.append("handler")
        return "hidden"

    parser.apply_setup(executable_flags=[ExecutableFlag("--flag", handler, display_result=False)])

    assert asyncio.run(parser.invoke_async(args=["--flag"])) is None
    assert calls == ["handler"]
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize(
    ("failure", "expected_code"),
    [
        (ConfigurationError("bad flag configuration"), ExitCode.CONFIGURATION),
        (UsageError("bad flag usage"), ExitCode.USAGE),
        (ValueError("flag failed"), ExitCode.INTERNAL),
    ],
)
def test_flag_failures_keep_parse_stage_error_classification(
    parser: Interfacy,
    mode: Literal["sync", "async"],
    failure: Exception,
    expected_code: ExitCode,
) -> None:
    def handler() -> None:
        raise failure

    async def async_handler() -> None:
        raise failure

    parser.apply_setup(
        executable_flags=[ExecutableFlag("--flag", handler if mode == "sync" else async_handler)]
    )
    runtime = parser._engine._runtime

    if mode == "sync":
        with pytest.raises(InvocationError) as e:
            runtime._invoke((), ["--flag"])
    else:
        with pytest.raises(InvocationError) as e:
            asyncio.run(runtime._invoke_async((), ["--flag"]))

    assert e.value.code == expected_code
    assert e.value.error is failure
    assert e.value.__cause__ is failure

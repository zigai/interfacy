import asyncio
import inspect as pyinspect
import warnings

import pytest

from interfacy import CommandGroup
from interfacy.core import InterfacyParser


class AsyncMath:
    def __init__(self, prefix: str = "math") -> None:
        self.prefix = prefix

    async def pow(self, base: int, exponent: int = 2) -> str:
        return f"{self.prefix}:{base**exponent}"


class AsyncOps:
    async def triple(self, value: int) -> int:
        return value * 3


class SyncLoopMath:
    def __init__(self, prefix: str = "math") -> None:
        self.prefix = prefix

    def pow(self, base: int, exponent: int = 2) -> str:
        async def _pow() -> str:
            return f"{self.prefix}:{base**exponent}"

        return asyncio.run(_pow())


def _assert_not_awaitable(result: object) -> None:
    assert not pyinspect.isawaitable(result)


def _assert_no_unawaited_runtime_warning(caught: list[warnings.WarningMessage]) -> None:
    assert not any(
        isinstance(item.message, RuntimeWarning) and "was never awaited" in str(item.message)
        for item in caught
    )


class TestAsyncExecution:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_async_function_command(self, parser: InterfacyParser) -> None:
        async def greet(name: str) -> str:
            return f"Hello, {name}!"

        parser.add_command(greet)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = parser.run(args=["Ada"])

        assert result == "Hello, Ada!"
        _assert_not_awaitable(result)
        _assert_no_unawaited_runtime_warning(caught)

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_async_class_subcommand(self, parser: InterfacyParser) -> None:
        parser.add_command(AsyncMath)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = parser.run(args=["pow", "2", "-e", "3"])

        assert result == "math:8"
        _assert_not_awaitable(result)
        _assert_no_unawaited_runtime_warning(caught)

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_async_bound_method_command(self, parser: InterfacyParser) -> None:
        parser.add_command(AsyncOps().triple)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = parser.run(args=["5"])

        assert result == 15
        _assert_not_awaitable(result)
        _assert_no_unawaited_runtime_warning(caught)

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_async_group_chain_leaf_execution(self, parser: InterfacyParser) -> None:
        workspace = CommandGroup("workspace")
        workspace.add_command(AsyncMath, name="amath")
        parser.add_command(workspace)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = parser.run(args=["workspace", "amath", "pow", "2", "-e", "3"])

        assert result == "math:8"
        _assert_not_awaitable(result)
        _assert_no_unawaited_runtime_warning(caught)


class TestSyncExecution:
    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_sync_function_can_call_asyncio_run(self, parser: InterfacyParser) -> None:
        def bootstrap(name: str) -> str:
            async def _bootstrap() -> str:
                return f"Hello, {name}!"

            return asyncio.run(_bootstrap())

        parser.add_command(bootstrap)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = parser.run(args=["Ada"])

        assert result == "Hello, Ada!"
        _assert_not_awaitable(result)
        _assert_no_unawaited_runtime_warning(caught)

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_sync_class_subcommand_can_call_asyncio_run(self, parser: InterfacyParser) -> None:
        parser.add_command(SyncLoopMath)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = parser.run(args=["pow", "2", "-e", "3"])

        assert result == "math:8"
        _assert_not_awaitable(result)
        _assert_no_unawaited_runtime_warning(caught)

    @pytest.mark.parametrize("parser", ["argparse_req_pos", "click_req_pos"], indirect=True)
    def test_sync_group_chain_leaf_can_call_asyncio_run(self, parser: InterfacyParser) -> None:
        workspace = CommandGroup("workspace")
        workspace.add_command(SyncLoopMath, name="smath")
        parser.add_command(workspace)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = parser.run(args=["workspace", "smath", "pow", "2", "-e", "3"])

        assert result == "math:8"
        _assert_not_awaitable(result)
        _assert_no_unawaited_runtime_warning(caught)

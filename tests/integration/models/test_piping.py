from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from interfacy import Interfacy


@dataclass
class PipedUser:
    name: str
    age: int


def test_piping_into_expanded_dataclass(pipe_stdin: Callable[[str], None]) -> None:
    """Verify piping JSON into a dataclass command with expand_model_params=True populates model."""

    def consume_user(user: PipedUser) -> PipedUser:
        return user

    cli = Interfacy(sys_exit_enabled=False)
    cli.add_command(consume_user, pipe_targets="user")

    payload = json.dumps({"name": "Alice", "age": 30})
    pipe_stdin(payload)

    assert cli.invoke(args=[]) == PipedUser(name="Alice", age=30)

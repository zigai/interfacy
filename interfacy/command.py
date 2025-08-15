from dataclasses import dataclass

from objinspect import Class, Function, Method


@dataclass
class Command:
    obj: Function | Method | Class
    name: str | None = None
    description: str | None = None
    pipe_target: dict[str, str] | str | None = None

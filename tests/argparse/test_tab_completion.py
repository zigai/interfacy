from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any, Literal

import pytest

from interfacy import CommandGroup, Interfacy
from interfacy.argparse_backend import Argparser


def _iter_actions(parser: Any) -> list[Any]:
    actions = list(getattr(parser, "_actions", ()))
    for action in list(actions):
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            for subparser in choices.values():
                actions.extend(_iter_actions(subparser))

    return actions


def _action_by_dest(parser: Any, suffix: str) -> Any:
    for action in _iter_actions(parser):
        dest = getattr(action, "dest", "")
        if dest == suffix or dest.endswith(f"__{suffix}"):
            return action

    raise AssertionError(f"No argparse action found for destination suffix: {suffix}")


def deploy(
    environment: Literal["dev", "staging", "prod"],
    *,
    fmt: Literal["json", "yaml"] = "json",
) -> str:
    return f"{environment}:{fmt}"


def paint(colors: list[Literal["red", "blue", "green"]]) -> list[str]:
    return colors


def collect(tag: list[Literal["red", "blue", "green"]] | None = None) -> list[str] | None:
    return tag


def test_tab_completion_installs_argcomplete_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Any] = []
    fake_argcomplete = SimpleNamespace(autocomplete=lambda parser: calls.append(parser))
    monkeypatch.setitem(sys.modules, "argcomplete", fake_argcomplete)

    parser = Argparser(tab_completion=True, sys_exit_enabled=False, print_result=False)
    parser.add_command(deploy)

    built_parser = parser.build_parser()

    assert calls == [built_parser]


def test_completion_metadata_includes_commands_aliases_and_literal_choices() -> None:
    group = CommandGroup("probe")
    group.add_command(deploy, aliases=("dep",))
    group.add_command(paint)

    parser = Interfacy(sys_exit_enabled=False, print_result=False)
    parser.add_command(group)
    built_parser = parser.build_parser()

    root_command = _action_by_dest(built_parser, "command")
    assert set(root_command.choices) == {"probe"}

    probe_command = _action_by_dest(built_parser, "probe__command")
    assert set(probe_command.choices) == {"deploy", "dep", "paint"}

    environment = _action_by_dest(built_parser, "environment")
    assert set(environment.choices) == {"dev", "staging", "prod"}

    fmt = _action_by_dest(built_parser, "fmt")
    assert set(fmt.choices) == {"json", "yaml"}

    colors = _action_by_dest(built_parser, "colors")
    assert set(colors.choices) == {"red", "blue", "green"}


def test_optional_list_literal_completion_metadata_keeps_choices() -> None:
    parser = Argparser(sys_exit_enabled=False, print_result=False)
    parser.add_command(collect)

    tag = _action_by_dest(parser.build_parser(), "tag")

    assert set(tag.choices) == {"red", "blue", "green"}


def test_future_annotations_class_method_literal_completion_matches_runtime_parser() -> None:
    namespace: dict[str, Any] = {}
    exec(
        "\n".join(
            [
                "from __future__ import annotations",
                "from typing import Literal",
                "class Tool:",
                "    def restart(",
                "        self,",
                "        service: Literal['api', 'worker', 'scheduler'],",
                "        force: bool = False,",
                "    ) -> str:",
                "        return service",
            ]
        ),
        namespace,
        namespace,
    )

    group = CommandGroup("probe")
    group.add_command(namespace["Tool"])
    parser = Interfacy(sys_exit_enabled=False, print_result=False)
    parser.add_command(group)

    service = _action_by_dest(parser.build_parser(), "service")
    assert set(service.choices) == {"api", "worker", "scheduler"}
    assert parser.run(args=["probe", "tool", "restart", "worker"]) == "worker"

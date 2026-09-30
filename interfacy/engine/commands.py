from __future__ import annotations

from objinspect import Class, Function, Method, Parameter, inspect

from interfacy.declarations.options import CommandOverrides
from interfacy.engine.settings import EngineSettings
from interfacy.introspection.annotations import resolve_objinspect_annotations
from interfacy.naming import NameMapping
from interfacy.runtime.invocation import CommandTarget
from interfacy.schema.model import Command


def inspect_command_target(
    target: CommandTarget,
    settings: EngineSettings,
    overrides: CommandOverrides,
) -> Function | Class | Method:
    """Inspect a command target, using ``settings`` for member filters ``overrides`` leave unset."""

    def pick(override: bool | None, default: bool) -> bool:
        return default if override is None else override

    inspected = inspect(
        target,
        init=True,
        public=True,
        inherited=pick(overrides.include_inherited_methods, settings.include_inherited_methods),
        static_methods=pick(overrides.include_staticmethods, settings.include_staticmethods),
        classmethod=pick(overrides.include_classmethods, settings.include_classmethods),
        protected=pick(overrides.include_protected_methods, settings.include_protected_methods),
        private=pick(overrides.include_private_methods, settings.include_private_methods),
    )
    resolve_objinspect_annotations(inspected)

    return inspected


def command_parameters(
    command: Command,
    subcommand: str | None,
    command_translator: NameMapping,
) -> dict[str, Parameter]:
    """Return the Python parameters of the callable a command and subcommand invoke."""
    obj = command.obj
    if isinstance(obj, (Function, Method)):
        return {parameter.name: parameter for parameter in obj.params}

    if not isinstance(obj, Class):
        return {}

    if subcommand in (None, "__init__"):
        method = obj.init_method
    else:
        method = next(
            (
                item
                for item in obj.methods
                if item.name == subcommand or command_translator.translate(item.name) == subcommand
            ),
            None,
        )

    return {} if method is None else {parameter.name: parameter for parameter in method.params}


__all__ = ["command_parameters", "inspect_command_target"]

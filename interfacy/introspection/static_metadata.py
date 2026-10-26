from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TypeGuard

import docstring_parser

from interfacy.common.sentinels import UNSET, UnsetType
from interfacy.exceptions import ConfigurationError
from interfacy.introspection.targets import ImportTarget, module_source_path

_GROUP_CLASS = "CommandGroup"
_GROUP_PARAMETERS = ("name", "description", "aliases")


@dataclass(frozen=True)
class StaticMetadata:
    """
    Command metadata read from a target's source without importing it.

    ``UNSET`` marks a value the source does not state as a literal.

    Attributes:
        name (str | UnsetType): Python name of a function or class, or a ``CommandGroup`` name.
        description (str | None | UnsetType): Description the imported target would report.
        aliases (tuple[str, ...]): Literal ``CommandGroup`` aliases.
        is_group (bool): Whether the source declares a ``CommandGroup``.
    """

    name: str | UnsetType = UNSET
    description: str | UnsetType | None = UNSET
    aliases: tuple[str, ...] = ()
    is_group: bool = False


def read_static_metadata(target: ImportTarget, *, group_factory: bool) -> StaticMetadata:
    """
    Read the metadata of ``target`` from its module source.

    With ``group_factory``, a function target is read as a factory returning a ``CommandGroup``.

    Raises:
        ConfigurationError: The module, its source, or the referenced object cannot be found.
    """
    try:
        path = module_source_path(target.module_ref)
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (ImportError, OSError, SyntaxError, ValueError) as e:
        raise ConfigurationError(f"Cannot read the source of command target '{target}': {e}") from e

    if "." in target.symbol_ref:
        return StaticMetadata()

    binding = _module_binding(tree, target.symbol_ref)
    if binding is None:
        raise ConfigurationError(f"'{target.symbol_ref}' is not defined in '{path}'")

    if isinstance(binding, (ast.Assign, ast.AnnAssign)):
        if _is_group_call(binding.value):
            return _group_metadata(binding.value, target)

        return StaticMetadata()

    if not isinstance(binding, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return StaticMetadata()

    if group_factory and not isinstance(binding, ast.ClassDef):
        call = _returned_group_call(binding)
        return StaticMetadata(is_group=True) if call is None else _group_metadata(call, target)

    return StaticMetadata(name=binding.name, description=_docstring_description(binding))


def _module_binding(tree: ast.Module, name: str) -> ast.stmt | None:
    found: ast.stmt | None = None
    for node in tree.body:
        if _binds(node, name):
            found = node

    return found


def _binds(node: ast.stmt, name: str) -> bool:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name == name
    if isinstance(node, ast.Assign):
        return any(isinstance(item, ast.Name) and item.id == name for item in node.targets)
    if isinstance(node, ast.AnnAssign):
        return isinstance(node.target, ast.Name) and node.target.id == name
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return any((alias.asname or alias.name.split(".")[0]) == name for alias in node.names)

    return False


def _is_group_call(node: ast.expr | None) -> TypeGuard[ast.Call]:
    if not isinstance(node, ast.Call):
        return False

    func = node.func
    if isinstance(func, ast.Name):
        return func.id == _GROUP_CLASS

    return isinstance(func, ast.Attribute) and func.attr == _GROUP_CLASS


def _factory_nodes(function: ast.FunctionDef | ast.AsyncFunctionDef) -> Iterator[ast.AST]:
    pending: list[ast.AST] = list(function.body)
    while pending:
        node = pending.pop()
        yield node

        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            pending.extend(ast.iter_child_nodes(node))


def _returned_group_call(function: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.Call | None:
    assigned: dict[str, list[ast.expr | None]] = {}
    mutated: set[str] = set()
    nodes = list(_factory_nodes(function))
    returned = [node.value for node in nodes if isinstance(node, ast.Return)]

    for node in nodes:
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for item in targets:
                if isinstance(item, ast.Name):
                    assigned.setdefault(item.id, []).append(
                        None if isinstance(node, ast.AugAssign) else node.value
                    )
                elif (
                    isinstance(item, ast.Attribute)
                    and isinstance(item.value, ast.Name)
                    and item.attr in _GROUP_PARAMETERS
                ):
                    mutated.add(item.value.id)

    calls: list[ast.Call] = []
    for value in returned:
        if isinstance(value, ast.Name):
            bindings = assigned.get(value.id, ())
            if len(bindings) != 1 or value.id in mutated:
                return None

            value = bindings[0]

        if not _is_group_call(value):
            return None

        calls.append(value)

    unique = list(dict.fromkeys(calls))

    return unique[0] if len(unique) == 1 else None


def _group_metadata(call: ast.Call, target: ImportTarget) -> StaticMetadata:
    if any(isinstance(arg, ast.Starred) for arg in call.args) or any(
        keyword.arg is None for keyword in call.keywords
    ):
        return StaticMetadata(is_group=True)

    arguments: dict[str, ast.expr] = dict(zip(_GROUP_PARAMETERS, call.args, strict=False))
    arguments.update(
        (keyword.arg, keyword.value) for keyword in call.keywords if keyword.arg is not None
    )

    name_node = arguments.get("name")
    name = UNSET if name_node is None else _literal(name_node)
    description_node = arguments.get("description")
    description = None if description_node is None else _literal(description_node)
    aliases_node = arguments.get("aliases")
    aliases = None if aliases_node is None else _literal(aliases_node)
    if not (aliases is None or isinstance(aliases, tuple)):
        raise ConfigurationError(
            f"CommandGroup aliases in '{target}' must be a literal tuple or list of strings"
        )

    return StaticMetadata(
        name=name if isinstance(name, str) else UNSET,
        description=description if description is None or isinstance(description, str) else UNSET,
        aliases=aliases or (),
        is_group=True,
    )


def _literal(node: ast.expr) -> str | tuple[str, ...] | UnsetType | None:
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return UNSET

    if value is None or isinstance(value, str):
        return value
    if isinstance(value, (tuple, list)) and all(isinstance(item, str) for item in value):
        return tuple(value)

    return UNSET


def _docstring_description(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> str | UnsetType | None:
    docstring = ast.get_docstring(node, clean=True)
    if docstring:
        parsed = docstring_parser.parse(docstring)
        return parsed.short_description or parsed.long_description or ""

    # Decorators can replace the docstring and base classes pass theirs on through
    # inspect.getdoc, so an empty source docstring does not prove an empty description.
    inherits = isinstance(node, ast.ClassDef) and any(
        not (isinstance(base, ast.Name) and base.id == "object") for base in node.bases
    )
    if node.decorator_list or inherits:
        return UNSET

    return None


__all__ = ["StaticMetadata", "read_static_metadata"]

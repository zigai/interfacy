---
name: interfacy
description: Build and review Interfacy Argparser CLIs for library users. Enforce strict public-API contracts, explicit banned patterns, fail-fast behavior, and correct help/parsing/runtime semantics.
---

# Interfacy Argparser Skill

Prioritize correct CLI behavior. Use only public API contracts. Enforce hard rules and explicit anti-pattern bans.

## Scope

- This skill is Argparser-only (`interfacy.Argparser`).
- This skill is public-API-only; do not depend on undocumented internals.
- If behavior is unclear from public docs/tests, ask the user before asserting semantics.

## Canonical snippets

Typed function command:

```python
from interfacy import Argparser

def greet(name: str, times: int = 1) -> str:
    return " ".join([f"Hello {name}"] * times)

def main() -> None:
    Argparser(print_result=True).run(greet)

if __name__ == "__main__":
    main()
```

Class namespace command:

```python
from interfacy import Argparser

class Math:
    def add(self, left: int, right: int) -> int:
        return left + right

Argparser(print_result=True).run(Math)
```

Expanded model flags:

```python
from dataclasses import dataclass
from interfacy import Argparser

@dataclass
class User:
    name: str
    age: int

def greet(user: User) -> str:
    return f"{user.name}:{user.age}"

Argparser(print_result=True).run(greet)
```

Explicit stdin piping:

```python
from interfacy import Argparser

def ingest(payload: str) -> str:
    return payload

Argparser().add_command(ingest, pipe_targets={"bindings": "payload", "priority": "pipe"})
```

CLI entrypoint target syntax:

```bash
interfacy path_or_module:symbol --help
```

## Hard rules: results vs exit codes

- Treat command return values (including `int`) as command results only, never process exit codes.
- Let Interfacy handle exit status internally.
- Keep `sys_exit_enabled=True` for end-user CLIs unless embedding/testing requires otherwise.
- Use `sys_exit_enabled=False` only when callers need to catch/inspect `SystemExit`.
- Never use `main(argv) -> int` + `raise SystemExit(main())` patterns for Interfacy command scripts.
- Never add wrappers that convert command return values into process exits.

## Hard rules: command modeling

- Use typed functions for leaf commands.
- Use classes when constructor options plus method subcommands are needed.
- Use class instances when constructor options must not be exposed on CLI.
- Use `CommandGroup` for explicitly shaped nested command trees.
- Use `@parser.command(...)` or `add_command(...)` consistently; both are valid.
- Keep command names and aliases unique.
- Do not repeatedly pass the same command objects to `run(*commands)` on an already configured parser.
- Do not define duplicate keys in `CommandGroup`.

## Hard rules: typing and parsing

- Add concrete type annotations for all user-facing CLI params.
- Use `list[T]` or `list[T] | None` when list nargs behavior is required.
- Do not use unions like `list[T] | X | None` when expecting list nargs behavior.
- Treat bool params as flag options.
- Use dataclass, Pydantic, or plain-class models for expansion when nested flags are desired.
- Use optional model types (`Model | None`) when absence of nested flags should resolve to `None`.
- Use model defaults intentionally; provided nested flags merge onto default model values.

## Hard rules: piping

- Configure piping with `pipe_targets` or `pipe_to(...)`.
- Use Python parameter names in pipe targets, not rendered CLI flag strings.
- Set `priority` explicitly: `cli` keeps CLI-provided values, `pipe` overrides them.
- Set `allow_partial=True` only when fewer chunks than targets is acceptable.
- Expect missing required pipe targets to fail fast.

## Hard rules: help behavior

- Choose help layout intentionally.
- Set `help_option_sort` and `help_subcommand_sort` when deterministic ordering matters.
- Pass sort rules as `list[str]` tokens, not single strings.
- Treat empty sort lists as default behavior.

## Hard rules: entrypoint targets

- Pass entrypoint targets as `module_or_file:symbol`.
- Use functions, classes, class instances, or bound methods as targets.
- Do not pass `Argparser` or `CommandGroup` objects as entrypoint targets.
- Use config defaults intentionally; they apply only when corresponding overrides are `None`.

## Hard rules: failure handling

- Let parse/runtime failures surface; do not mask them with broad exception wrappers.
- Do not add broad `except SystemExit` handlers that hide failures.
- Treat `SystemExit(0)` help flows and `SystemExit(2)` parse failures as distinct outcomes.

## Banned patterns

- Do not execute CLI at import time (`cli()` at module top level).
- Do not use mutable default lists/dicts in command signatures.
- Do not rely on alias names appearing in usage-choice braces.

## Light verification checklist

- Confirm help path behavior with `--help` on root and subcommands.
- Confirm parse failures surface as parse errors (not swallowed).
- Confirm command return values print/flow as results, not exit codes.
- Confirm piping behavior for required targets and chosen `priority`.

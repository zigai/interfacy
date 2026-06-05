---
name: interfacy
description: Use when designing, building, reviewing, or refactoring Python CLIs with Interfacy.
---

# Interfacy

Interfacy is a Python CLI framework that builds command-line interfaces from existing typed functions, classes, class instances, signatures, defaults, and docstrings.

Use it when a project needs a CLI without maintaining a separate parser tree. The normal workflow is to reuse or lightly shape ordinary Python callables, then pass them to `Interfacy`.

## Installation

### From PyPI

```bash
pip install interfacy
```

```bash
uv add interfacy
```

## Basic Usage

```python
from interfacy import Interfacy

def greet(name: str, times: int = 1) -> None:
    """Print a greeting.

    Args:
        name: Person to greet.
        times: Number of greetings.
    """
    print(" ".join(f"Hello, {name}!" for _ in range(times)))

if __name__ == "__main__":
    Interfacy().run(greet)
```

```text
$ python app.py Ada --times 2
Hello, Ada! Hello, Ada!
```

## Usage Strategy

1. Choose the shape that matches the user's CLI:
   - One action: a typed function.
   - Several related actions sharing setup: a class.
   - Existing service object or injected dependencies: a class instance.
   - A manually composed command tree: `CommandGroup`.
2. Reuse existing typed functions, classes, or instances when they already express the command behavior. Do not create new wrapper functions just to satisfy Interfacy.
3. Make the callable signature describe the CLI:
   - Required inputs are positional parameters.
   - Options are keyword/defaulted parameters, often keyword-only.
   - Choices are `Literal[...]` or `Enum`.
   - Repeated values are `list[T]` or variadic parameters.
   - Grouped settings are small dataclasses, Pydantic models, or typed config classes.
   - Domain-specific scalar values can use `Interfacy.add_type_parser(...)` when a plain annotation is not enough.
4. Put user-facing help in docstrings. The first line should read like command help, not implementation notes. Do not duplicate default values in docstrings; Interfacy can show defaults from signatures.
5. Wire with the public API:

```python
from interfacy import Interfacy

Interfacy(print_result=True).run(command)
```

## What Good Interfacy Code Looks Like

- The command function can be called normally from Python tests.
- Existing functions/classes are reused directly when their signatures and docstrings are already CLI-ready.
- The CLI does not duplicate parameter names, defaults, choices, or help in a second parser definition.
- Parsing concerns stay at the boundary; business logic stays in ordinary Python functions/classes.
- Return values are meaningful Python values. Use `print_result=True` when the CLI should display them.
- Return values, including integers, are command results, not process exit codes.
- Existing printed output, file writes, network calls, and exit behavior are preserved intentionally.

## What To Avoid

- Do not recreate parser trees by hand when Interfacy can infer them.
- Use the public `Interfacy` API for normal application code.
- Do not add manual printing just to show a returned value.
- Do not add thin wrappers around existing callables unless adapting names, validation, parser-specific inputs, or user-facing behavior actually requires it.
- Do not wrap Interfacy entrypoints in `raise SystemExit(main())` patterns that reinterpret command results as exit codes.
- Do not run `.run(...)` at import time; guard executable entrypoints with `if __name__ == "__main__":`.
- Do not hide parse or runtime failures with broad `except Exception` or `except SystemExit` wrappers.
- Do not hide CLI-only transformations in decorators or global state; put them in the callable body or a small adapter.
- Do not expose every method or field of a domain object just because Interfacy can. Design the CLI surface deliberately.

## References

- Read `references/api-patterns.md` when choosing between functions, classes, decorators, command groups, custom type parsers, entrypoints, result display, or tests.
- Read `references/structured-parameters.md` when a command has grouped/nested inputs or config objects.
- For large CLIs with many commands, use `CommandGroup` for real command namespaces and `help_group` constants for readable top-level help sections.

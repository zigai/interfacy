# Repository guidance

Interfacy builds command-line interfaces from typed Python functions, methods, classes, and instances. `interfacy.Interfacy` is the public facade. It registers commands, builds a backend-neutral schema, parses arguments with argparse or optional Click, and invokes the selected callable.

## Common Commands

Run a single test file or test directly:

```bash
uv run --group test pytest tests/unit/schema/test_method_dispatch.py -q
uv run --group test pytest tests/unit/schema/test_method_dispatch.py::test_name -q
```

## Architecture

`Interfacy` in `interfacy/app.py` is the facade. It delegates to `core/`, which builds a `ParserSchema` with `schema/builder/`, compiles it through a backend adapter from `backends/registry.py`, and executes via `runtime/invocation.py` and `runtime/runner.py`.

Packages are layered, lowest first; a module may import only from its own or a lower layer:

`common` → `exceptions` → `introspection` → `models` → `declarations` → `naming` → `schema` → `help` → `plugins` → {`backends` | `runtime`} → `core` → `app` → `cli`

- `common/`: console output, debug logging, terminal width, sentinels.
- `introspection/`: annotation analysis, choices, default type parser. `models/`: dataclass/Pydantic/plain-class adapters.
- `declarations/`: user-declared objects (`Param`, `CommandGroup`, `ExecutableFlag`, `PipeTargets`, sort rules, shared setting types and validators).
- `schema/`: `nodes.py` contracts, `values.py` plans, `conversion.py`, `validation.py`, and the `builder/` package.
- `help/`: content, `layouts/` (HelpLayout + presets), sorting, formatting, rendering.
- `plugins/`: plugin base classes, hook contexts, descriptors, recovery actions.
- `backends/`: adapter protocols (`base.py`), lazy registry, `argparse/` and `click/` (Click is optional).
- `runtime/`: invocation, runner, piping, model reconstruction, executable flags, exit/interrupt policy.
- `core/`: `InterfacyCore`, settings, registry, plugin manager, compiler/cache, recovery, help pipeline, snapshots.
- `cli/`: the repository's own `interfacy` command, target resolution, and config loading.

`tests/contracts/test_dependencies.py` enforces the layers, keeps `backends` and `runtime` independent, and forbids function-local `interfacy.*` imports (except the lazy backend registry). Public API changes go through `interfacy/__init__.py` (`_EXPORTS`, the `TYPE_CHECKING` block, `__all__`).

## Code Style

- Support Python 3.11 and newer. Use `list`, `dict`, and `set` annotations and `T | None` unions.
- Use absolute imports and Google-style docstrings with D213 multi-line layout.
- Keep lines within 100 characters. Prefer early returns and minimal nesting.
- Keep signatures plain Python. Never require `Annotated[...]` or other CLI markers in a signature. Infer from names, types, and defaults, configure on the plugin by parameter reference, or use `@params` or `CommandOptions`.

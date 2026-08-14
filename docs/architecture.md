# Architecture

Interfacy has one public facade and four internal layers. New code should follow these ownership boundaries rather than adding behavior to `InterfacyParser` or a backend parser.

## Composition

`interfacy.Interfacy` is the public entry point. It validates user configuration through
`engine.settings.EngineSettings`, selects a backend adapter, and delegates command
registration, schema construction, parsing, and execution.

Shared lifecycle ownership is split across cohesive components:

- `engine.settings`: validated parser construction settings
- `engine.registry`: commands, aliases, and command-name registration
- `engine.plugins`: portable and backend-native plugin registration, hooks, snapshots, and parse recovery
- `runtime.context`: explicit command-execution dependencies
- `runtime.policy`: CLI-only result, error, and interrupt presentation

Backends translate a `ParserSchema` into backend-native parser objects. Runtime execution
receives an explicit `runtime.context.ExecutionContext`; it does not reach back into a parser
for commands, naming, piping, or type conversion.

## Package ownership

| Package | Owns | Must not own |
| --- | --- | --- |
| `schema` | Backend-neutral command and argument contracts, inspection, type/value plans, schema validation | Backend objects, terminal rendering, runtime execution |
| `help` | Layout policy, type/default formatting, sorting presentation, terminal measurement, schema rendering | Command discovery, parsing, execution |
| `runtime` | Invocation, piped-value application, result display, exit and interrupt policy | Backend compilation, command registration |
| `argparse_backend` | Argparse compilation, parsing, and argparse-specific failures | Shared execution policy |
| `click_backend` | Click compilation, parsing, help attachment, and Click compatibility | Shared execution policy |
| `cli` | The repository's own `interfacy` command target and configuration loading | Framework internals |

## Dependency direction

The stable direction is:

```text
public facade -> engine -> schema
                     \-> selected backend -> schema + help
                     \-> runtime -> schema
help -> schema
```

Schema contracts, runtime modules, and help modules may not import concrete backends. Backends may not import the public facade. `tests/contracts/test_dependencies.py` enforces these rules.

## Change placement

- Add a new callable or model inspection rule to `schema`.
- Add backend-neutral invocation behavior to `runtime`.
- Add output formatting or width behavior to `help`.
- Add parser-library translation only to the corresponding backend.
- Add lifecycle state to an existing engine owner; do not add another forwarding manager.

Public API changes must update `interfacy/__init__.py`, `interfacy/__init__.pyi`, relevant API documentation, and installed-wheel verification together.

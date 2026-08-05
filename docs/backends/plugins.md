# Plugins

Plugins let code hook into Interfacy's parser lifecycle.

Plugins run at the CLI boundary rather than inside one command function.

```python
from interfacy import Interfacy
from interfacy.plugins import InterfacyPlugin, PluginContext


class TraceArgs(InterfacyPlugin):
    name = "trace-args"

    def before_parse(self, context: PluginContext, args: list[str]) -> list[str]:
        print("raw args:", args)
        return args


Interfacy(plugins=[TraceArgs()]).run(main)
```

## Lifecycle

A plugin can implement any of these hooks:

| Hook | Purpose |
| --- | --- |
| `configure()` | configure the parser immediately after registration |
| `before_parse()` | rewrite raw CLI args before backend parsing |
| `after_parse()` | rewrite the parsed namespace |
| `transform_schema()` | adjust the built schema before backend materialization |
| `wrap_execute()` | wrap command execution |
| `recover_parse_failure()` | provide values or subcommands for recoverable parse failures |

Hooks receive a `PluginContext` with parser, backend, schema, args, namespace, and metadata where relevant.

## Execution wrappers

`wrap_execute()` is useful for timing, tracing, transactions, or context setup.

```python
from collections.abc import Callable
from typing import Any


class TimingPlugin(InterfacyPlugin):
    def wrap_execute(self, context: PluginContext, call_next: Callable[[], Any]) -> Any:
        print("starting")
        try:
            return call_next()
        finally:
            print("done")
```

## Parse recovery

A recovery plugin can supply missing arguments or a missing subcommand.

```python
from interfacy.plugins import ProvideArgumentValues


class DefaultsPlugin(InterfacyPlugin):
    def recover_parse_failure(self, context, failure):
        if not failure.missing_arguments:
            return None

        values = {ref: "default" for ref in failure.missing_arguments if ref.argument.type is str}
        return ProvideArgumentValues(values=values) if values else None
```

Limit recovery loops with `parse_recovery_max_attempts`.

```python
Interfacy(
    plugins=[DefaultsPlugin()],
    parse_recovery_max_attempts=1,
).run(main)
```

## Registration

Register plugins in the constructor, with `apply_setup()`, or with `add_plugin()`.

```python
parser = Interfacy()
parser.add_plugin(TraceArgs())
parser.run(main)
```

Plugin names must be unique per parser. If `name` is not set, the class name is used.

For API details, see {doc}`../reference/plugins`.

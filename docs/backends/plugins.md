# Plugins

Plugins let code hook into Interfacy's parser lifecycle.

Plugins run at the CLI boundary rather than inside one command function.

```python
from interfacy import Interfacy
from interfacy.plugins import BeforeParseContext, InterfacyPlugin


class TraceArgs(InterfacyPlugin):
    name = "trace-args"

    def before_parse(
        self,
        context: BeforeParseContext,
        args: tuple[str, ...],
    ) -> tuple[str, ...]:
        print("raw args:", args)
        return args


Interfacy(plugins=[TraceArgs()]).run(main)
```

## Lifecycle

Portable plugins subclass `InterfacyPlugin` and can implement these hooks:

| Hook | Purpose |
| --- | --- |
| `configure()` | register portable capabilities immediately after registration |
| `before_parse()` | rewrite raw CLI args before backend parsing |
| `after_parse()` | rewrite the parsed namespace |
| `transform_schema()` | replace the built schema before backend materialization |
| `transform_help()` | replace structured help sections before terminal rendering |
| `wrap_execute()` | wrap command execution |
| `recover_parse_failure()` | provide values or subcommands for recoverable parse failures |

Each hook receives a context dataclass tailored to that lifecycle phase. Portable
contexts expose only backend-neutral state and capabilities, such as the backend name,
metadata, schema descriptors, raw arguments, or parsed namespaces. Metadata and namespace
containers are copied into read-only mappings when the context is constructed. Plugins
must return replacements from transformation hooks rather than reaching into parser
internals.

## Help transformation

`transform_help()` receives backend-neutral, immutable help content after Interfacy has
built the usage, description, positional, option, command, and epilog sections, but before
they are joined into terminal text. Return a new `HelpContent` to remove, reorder, replace,
or append sections without depending on argparse or Click formatter internals.

```python
from interfacy.help import HelpContent, HelpSection
from interfacy.plugins import HelpHookContext


class ConciseHelpPlugin(InterfacyPlugin):
    def transform_help(
        self,
        context: HelpHookContext,
        content: HelpContent,
    ) -> HelpContent:
        sections = tuple(section for section in content.sections if section.kind != "options")
        return HelpContent((*sections, HelpSection("epilog", "See the online manual.")))
```

Each `HelpSection` has a stable `kind` (`usage`, `description`, `positionals`, `options`,
`commands`, or `epilog`) and its rendered text. `HelpHookContext` identifies the program,
terminal width, current command path, and a schema descriptor.


## Backend-native plugins

Subclass `BackendPlugin` only when a plugin must use argparse or Click objects directly.
Declare the required backend and implement `configure_backend()`:

```python
from interfacy.plugins import BackendPlugin, BackendPluginContext


class ArgparseNativePlugin(BackendPlugin):
    backend = "argparse"

    def configure_backend(self, context: BackendPluginContext) -> None:
        adapter = context.adapter
        native_parser = context.native_parser
```

`BackendPluginContext` deliberately exposes the selected adapter and native parser. This is
an explicit compatibility boundary: backend-native plugins are tied to that backend's
semantics and may require changes when its integration changes. Registering one against the
wrong backend raises `ConfigurationError`.


## Execution wrappers

`wrap_execute()` is useful for timing, tracing, transactions, or context setup.

```python
from collections.abc import Callable
from typing import Any
from interfacy.plugins import ExecuteContext


class TimingPlugin(InterfacyPlugin):
    def wrap_execute(self, context: ExecuteContext, call_next: Callable[[], Any]) -> Any:
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

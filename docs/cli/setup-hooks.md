# Setup Hooks

A target module can define `configure_interfacy(parser)` to customize the parser used by the `interfacy` entrypoint.

```python
# app.py
from interfacy import Interfacy
from interfacy.help import Modern


def configure_interfacy(parser: Interfacy) -> None:
    parser.apply_setup(
        help_layout=Modern(),
        print_result=True,
    )


def greet(name: str) -> str:
    """Return a greeting."""
    return f"Hello, {name}!"
```

```console
$ interfacy app.py:greet Ada
Hello, Ada!
```

The hook runs after entrypoint configuration is loaded and before the target object is registered.

## Register plugins

Hooks are a good place to add project-local plugins.

```python
from interfacy.plugins import BeforeParseContext, InterfacyPlugin


class TracePlugin(InterfacyPlugin):
    def before_parse(
        self,
        context: BeforeParseContext,
        args: tuple[str, ...],
    ) -> tuple[str, ...]:
        print("args:", args)
        return args


def configure_interfacy(parser: Interfacy) -> None:
    parser.add_plugin(TracePlugin())
```

## Register type parsers

Hooks can also register custom type parsers.

```python
class Port:
    def __init__(self, value: int) -> None:
        self.value = value


def configure_interfacy(parser: Interfacy) -> None:
    parser.add_type_parser(Port, lambda raw: Port(int(raw)))
```

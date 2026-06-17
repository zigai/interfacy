# Schema overview

Interfacy builds a schema before it builds a backend parser.

The schema is a backend-independent description of the CLI: parser metadata, commands, parameters, choices, boolean behavior, pipe targets, executable flags, and help configuration.

```python
from interfacy import Interfacy


def greet(name: str, excited: bool = False) -> str:
    """Return a greeting."""
    return f"Hello, {name}{'!' if excited else '.'}"


parser = Interfacy()
parser.add_command(greet)
schema = parser.build_parser_schema()
```

## Main objects

| Object | Purpose |
| --- | --- |
| `ParserSchema` | complete CLI parser description |
| `Command` | one command or command namespace |
| `Argument` | one parameter or synthetic help/executable flag row |
| `ArgumentKind` | positional vs option classification |
| `ValueShape` | single, list, tuple, or flag value shape |
| `BooleanBehavior` | generated boolean flag metadata |

## Backend independence

The same schema can feed the argparse or Click backend. Backend-specific parser objects are built after schema generation.

This is why plugins that use `transform_schema()` can work across backends.

## API details

See {doc}`../api/schema` for generated details on schema classes and pipe input types.

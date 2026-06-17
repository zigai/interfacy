# Why Interfacy?

Interfacy exists for code that already has a good Python interface and only needs a command-line interface around it.

A command is usually already hiding in your code:

```python
def resize(path: str, width: int, height: int, overwrite: bool = False) -> None:
    """Resize an image."""
```

The function name, parameter names, annotations, defaults, and docstring already say most of what a CLI parser needs to know. Interfacy uses that information directly instead of asking you to duplicate it in another parser definition.

## What you keep

The callable remains an ordinary callable.

```python
def greet(name: str, excited: bool = False) -> str:
    """Build a greeting."""
    suffix = "!" if excited else "."
    return f"Hello, {name}{suffix}"
```

Expose the callable as a CLI:

```python
from interfacy import Interfacy

Interfacy(print_result=True).run(greet)
```

```text
$ python app.py Ada --excited
Hello, Ada!
```

It is still a normal Python function, so tests can call it directly:

```python
def test_greet() -> None:
    assert greet("Ada", excited=True) == "Hello, Ada!"
```

## What Interfacy adds

Interfacy provides the CLI boundary around those objects:

- parser construction
- command routing
- type conversion
- nested subcommands
- generated help
- stdin routing
- tab completion metadata
- configurable output style
- plugin hooks

The Python object remains the source of truth for command shape and help text.

## Argparse-compatible parser

Interfacy also includes an `ArgumentParser` wrapper for manually shaped parser trees.

It follows the regular argparse workflow: create a parser, call `add_argument()`, and parse arguments. The wrapper adds Interfacy help rendering, layout and color configuration, custom help flags, and nested destination handling.

See {doc}`../backends/argparse-wrapper`.

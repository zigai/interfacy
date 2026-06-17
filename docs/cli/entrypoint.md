# Entrypoint

Interfacy ships a CLI named `interfacy`.

It can run a function, class, or class instance directly from a Python file or importable module.

```console
$ interfacy app.py:greet Ada
$ interfacy app.py:greet --help
$ interfacy package.cli:Calculator add 1 2
```

The target format is:

```text
module_or_path:symbol
```

Examples:

```console
$ interfacy main.py:main
$ interfacy package.cli:main
$ interfacy package.cli:Tool
$ interfacy package.cli:service
```

## Function targets

```python
# app.py

def greet(name: str, times: int = 1) -> None:
    """Print a greeting."""
    for _ in range(times):
        print(f"Hello, {name}!")
```

```console
$ interfacy app.py:greet Ada --times 2
Hello, Ada!
Hello, Ada!
```

## Class targets

```python
# app.py

class Math:
    def add(self, left: int, right: int) -> int:
        """Add two numbers."""
        return left + right
```

```console
$ interfacy app.py:Math add 2 3
```

Configuration can enable `print_result` for returned values. See {doc}`config`.

## Passing through `--`

`--` separates entrypoint arguments from target-command arguments.

```console
$ interfacy app.py:main -- --target-value
```

## Special flags

The entrypoint itself supports:

```console
$ interfacy --help
$ interfacy --version
$ interfacy --config-paths
```

Use `interfacy TARGET --help` for target help.

## Supported targets

The entrypoint accepts objects that Interfacy can register as commands: functions, classes, methods, and instances.

It intentionally does not accept parser instances or `CommandGroup` objects as entrypoint targets. Build those in a small script when you need a manually assembled tree.

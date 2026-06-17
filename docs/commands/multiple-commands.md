# Multiple Commands

Pass more than one command target to `run()` to build a multi-command CLI.

```python
from interfacy import Interfacy


def build() -> str:
    """Build the project."""
    return "built"


def clean() -> str:
    """Remove build artifacts."""
    return "clean"


if __name__ == "__main__":
    Interfacy(print_result=True).run(build, clean)
```

```console
$ python project.py build
built

$ python project.py clean
clean
```

The command name is derived from the function name and translated to kebab-case.

```python
def list_files() -> None:
    """List files."""
```

```console
$ python project.py list-files
```

## Register first, run later

For larger applications, register commands explicitly.

```python
parser = Interfacy(print_result=True)
parser.add_command(build)
parser.add_command(clean)
parser.run()
```

This form is useful when commands are assembled from different modules.

## Decorator registration

`command()` keeps registration near the command definition.

```python
parser = Interfacy(print_result=True)


@parser.command(name="fmt")
def format_code(check: bool = False) -> str:
    """Format code."""
    return "checked" if check else "formatted"


parser.run()
```

The decorated object is returned unchanged, so it remains a normal Python function.

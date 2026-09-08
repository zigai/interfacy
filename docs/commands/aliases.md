# Aliases

Aliases let one command respond to more than one CLI name.

```python
from interfacy import Interfacy


def build(release: bool = False) -> str:
    """Compile the project."""
    return "release" if release else "debug"


def status() -> str:
    """Report project status."""
    return "ready"


parser = Interfacy(print_result=True)
parser.add_command(build, aliases=("b",))
parser.add_command(status)
parser.run()
```

```console
$ python project.py build
$ python project.py b
```

The canonical name is still `build`. The alias is only another way to select it from the command line.
The second command creates a command-selection root. A lone function is flattened into
the root and is invoked without its command name.

## Group aliases

`CommandGroup` also accepts aliases.

```python
from interfacy import CommandGroup

ops = CommandGroup("operations", aliases=("ops",))
```

And commands inside groups can have aliases:

```python
ops.add_command(build, aliases=("b",))
```

```console
$ python app.py ops b
```

## Name translation

Python names are translated to kebab-case by default.

```python
def show_status() -> str:
    """Show status."""
    return "ok"
```

```console
$ python app.py show-status
```

If you need stable public names that are different from Python names, prefer `name=` and `aliases=` over renaming the Python function only for CLI aesthetics.

```python
parser.add_command(show_status, name="status", aliases=("st",))
```

# Groups

`CommandGroup` builds a CLI tree explicitly instead of deriving the full shape from one function or class.

```python
from interfacy import CommandGroup, Interfacy


def clone(url: str) -> str:
    """Clone a repository."""
    return f"clone {url}"


class Releases:
    """Release commands."""

    def cut(self, version: str) -> str:
        """Cut a release."""
        return f"cut {version}"


ops = CommandGroup("ops", description="Operational commands")
ops.add_command(clone)
ops.add_command(Releases)

Interfacy(print_result=True).run(ops)
```

```console
$ python app.py ops clone https://example.com/repo.git
clone https://example.com/repo.git

$ python app.py ops releases cut 1.2.0
cut 1.2.0
```

## Group arguments

A group can have parent options using `with_args()`.

```python
class GlobalOptions:
    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose


tools = CommandGroup("tools").with_args(GlobalOptions)
```

Those options live on the group node and are parsed before subcommand execution.

## Group methods

`CommandGroup.add_command()` accepts the same targets as `Interfacy.add_command()`:

- functions
- classes
- class instances
- bound methods
- nested command groups through `add_group()`

Groups keep the command tree explicit rather than inferred from one class.

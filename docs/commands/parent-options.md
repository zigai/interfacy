# Parent Options

Class initializers and group arguments create parent options.

```python
from interfacy import Interfacy


class Math:
    def __init__(self, rounding: int = 2) -> None:
        self.rounding = rounding

    def add(self, left: float, right: float) -> float:
        """Add two numbers."""
        return round(left + right, self.rounding)


Interfacy(print_result=True).run(Math)
```

```console
$ python calc.py --rounding 3 add 1.2345 2.3445
3.579
```

## Late parent options

Initializer options can also appear after the subcommand when there is no ambiguity.

```console
$ python calc.py add 1.2345 2.3445 --rounding 3
```

This is helpful for CLIs where users naturally type the action first.

## Nearest command wins

If a parent and a child both accept the same option name, an option after the subcommand belongs to the child.

```python
class Tool:
    def __init__(self, mode: str = "parent") -> None:
        self.mode = mode

    def run(self, mode: str = "child") -> tuple[str, str]:
        return self.mode, mode
```

```console
$ python app.py run --mode leaf
```

`--mode leaf` belongs to `run`, not to the initializer. Put parent options before the subcommand when you need to disambiguate.

## Group options

Groups can define parent options with `with_args()`.

```python
from interfacy import CommandGroup


class GlobalArgs:
    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose


group = CommandGroup("tools").with_args(GlobalArgs)
```

Parent options apply configuration to a command namespace, such as output format, profile, host, or verbosity.

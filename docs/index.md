# Interfacy

Interfacy turns ordinary Python functions, classes, methods, and instances into command-line interfaces. It reads signatures, type annotations, defaults, and docstrings so your command behavior and your CLI contract stay in one place.

```{toctree}
:hidden:
:caption: Documentation
:maxdepth: 2

Quickstart <basics/quickstart>
Why Interfacy? <why/index>
Commands <commands/index>
Types <types/index>
Help <help/index>
Runtime <runtime/index>
CLI <cli/index>
Backends <backends/index>
Reference <reference/index>
```

```{toctree}
:hidden:
:caption: Links
:maxdepth: 1

Contributing <contributing>
Architecture <architecture>
License <license>
PyPI <https://pypi.org/project/interfacy/>
GitHub <https://github.com/zigai/interfacy>
Issues <https://github.com/zigai/interfacy/issues>
```

## Features

- Commands from functions, methods, classes, and instances.
- Nested command trees from classes and `CommandGroup`.
- Type conversion from annotations, including primitives, booleans, sequences, choices, models, and custom parsers.
- Help text from docstrings with configurable layouts, colors, grouping, and sorting.
- Runtime support for stdin, argument files, shell completion, exit codes, and interrupts.
- Default argparse backend and optional Click backend.

## Install

```bash
pip install interfacy
```

```bash
uv add interfacy
```

## Basic usage

```python
from interfacy import Interfacy


def greet(name: str, times: int = 1) -> None:
    """Print a greeting."""
    for _ in range(times):
        print(f"Hello, {name}!")


if __name__ == "__main__":
    Interfacy().run(greet)
```

```text
$ python app.py Ada --times 2
Hello, Ada!
Hello, Ada!
```

Required non-boolean parameters become positionals. Optional parameters become flags. Boolean parameters become toggles. Docstrings provide help text.

## Documentation

- [Quickstart](basics/quickstart.md)
- [Why Interfacy?](why/index.md)
- [Commands](commands/index.md)
- [Types](types/index.md)
- [Help](help/index.md)
- [Runtime](runtime/index.md)
- [CLI](cli/index.md)
- [Backends](backends/index.md)
- [Reference](reference/index.md)
- [Architecture](architecture.md)

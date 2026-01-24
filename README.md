# Interfacy

[![PyPI version](https://badge.fury.io/py/interfacy.svg)](https://badge.fury.io/py/interfacy)
![Supported versions](https://img.shields.io/badge/python-3.10+-blue.svg)
[![Downloads](https://static.pepy.tech/badge/interfacy)](https://pepy.tech/project/interfacy)
[![license](https://img.shields.io/github/license/zigai/interfacy.svg)](https://github.com/zigai/interfacy/blob/main/LICENSE)

Interfacy is a CLI framework for building command-line interfaces from Python functions, classes, and class instances using type annotations and docstrings.

## Features

- Generate CLIs from functions, class methods, or class instances.
- Nested subcommands and command groups with aliases.
- Type inference from annotations, with support for custom parsers.
- Multiple help layouts and color themes.
- Optional class initializer arguments exposed as CLI options.
- Argparse-compatible backend, including a drop-in `ArgumentParser` replacement.
- Stdin piping support with configurable routing to parameters.
- Optional tab completion via `argcomplete`.

## Installation

### From PyPI

```bash
pip install interfacy
```

```bash
uv add interfacy
```

### From source

```bash
pip install git+https://github.com/zigai/interfacy.git
```

```bash
uv add "git+https://github.com/zigai/interfacy.git"
```

## Quick start

```python
from interfacy import Argparser

def greet(name: str, times: int = 1) -> None:
    for _ in range(times):
        print(f"Hello, {name}!")

if __name__ == "__main__":
    Argparser().run(greet)
```

## Class-based commands

```python
from interfacy import Argparser

class Math:
    def add(self, left: int, right: int) -> int:
        return left + right

    def mul(self, left: int, right: int) -> int:
        return left * right

if __name__ == "__main__":
    Argparser(print_result=True).run(Math)
```

## License

[MIT License](https://github.com/zigai/interfacy/blob/main/LICENSE)

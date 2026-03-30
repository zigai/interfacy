# Interfacy

[![Tests](https://github.com/zigai/interfacy/actions/workflows/tests.yml/badge.svg)](https://github.com/zigai/interfacy/actions/workflows/tests.yml)
[![PyPI version](https://badge.fury.io/py/interfacy.svg)](https://badge.fury.io/py/interfacy)
![Supported versions](https://img.shields.io/badge/python-3.10+-blue.svg)
[![Downloads](https://static.pepy.tech/badge/interfacy)](https://pepy.tech/project/interfacy)
[![license](https://img.shields.io/github/license/zigai/interfacy.svg)](https://github.com/zigai/interfacy/blob/main/LICENSE)

Interfacy is a CLI framework that turns Python functions, classes, and class instances into command-line interfaces. It derives the CLI from signatures, type annotations, and docstrings instead of making you define it twice.

## Features

- Generate CLIs from functions, classes, class methods, and class instances.
- Nested subcommands and manual command groups with aliases.
- Type-driven parsing from annotations, with support for custom parsers.
- Model expansion for dataclasses, Pydantic models, and plain classes.
- `--help` text generated from docstrings.
- Highly customizable help output with multiple layouts, color themes, and configurable ordering.
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

## First CLI

```python
from interfacy import Argparser

def greet(name: str, times: int = 1) -> str:
    """Return a greeting."""
    return " ".join([f"Hello, {name}!" for _ in range(times)])

if __name__ == "__main__":
    Argparser(print_result=True).run(greet)
```

```text
$ python app.py Ada
Hello, Ada!

$ python app.py Ada --times 2
Hello, Ada! Hello, Ada!
```

By default, required non-boolean parameters become positional arguments and optional parameters become flags.

## Class-Based Commands

Classes become command namespaces. `__init__` parameters live at the command level and public methods become subcommands.

```python
from interfacy import Argparser

class Calculator:
    def __init__(self, precision: int = 2) -> None:
        self.precision = precision

    def add(self, a: float, b: float) -> float:
        return round(a + b, self.precision)

    def mul(self, a: float, b: float) -> float:
        return round(a * b, self.precision)

if __name__ == "__main__":
    Argparser(print_result=True).run(Calculator)
```

```text
$ python app.py --precision 3 add 1.25 2.75
4.0
```

## Structured Parameters

Dataclasses, Pydantic models, and plain classes with typed `__init__` parameters can be expanded into nested flags and reconstructed before execution.

```python
from dataclasses import dataclass
from interfacy import Argparser

@dataclass
class Address:
    city: str
    postal_code: int

@dataclass
class User:
    name: str
    age: int
    address: Address | None = None

def greet(user: User) -> str:
    return f"Hello {user.name}, age {user.age}"

if __name__ == "__main__":
    Argparser(print_result=True).run(greet)
```

```text
$ python app.py --user.name Ada --user.age 32
Hello Ada, age 32
```

## Manual Groups

Use `CommandGroup` when your command tree is not naturally rooted in one callable:

```python
from interfacy import Argparser, CommandGroup

def clone(url: str) -> str:
    return f"clone:{url}"

class Releases:
    def cut(self, version: str) -> str:
        return f"cut:{version}"

ops = CommandGroup("ops", description="Operational commands")
ops.add_command(clone)
ops.add_command(Releases)

if __name__ == "__main__":
    Argparser(print_result=True).run(ops)
```

## Interfacy CLI Entrypoint

Interfacy also ships a CLI that can run an existing function, class, or class instance directly from a module or Python file:

```text
$ interfacy app.py:greet Ada
$ interfacy app.py:greet --help
$ interfacy package.cli:Calculator add 1 2
```

The entrypoint supports configuration via TOML, loaded from `~/.config/interfacy/config.toml` or `INTERFACY_CONFIG`.

```text
usage: interfacy [--help] [--version] [--config-paths] [TARGET] ...

Interfacy is a CLI framework for building command-line interfaces from Python callables.

positional arguments:
  TARGET                      Python file or module with a function/class/instance symbol (e.g. main.py:main, pkg.cli:App, pkg.cli:service).
  ARGS                        Arguments passed through to the target command.

options:
  --help                      show this help message and exit
  --version                   show version and exit.
  --config-paths              print config file search paths and exit.

Use 'interfacy TARGET --help' to display the help text for the target.
```

## License

[MIT License](https://github.com/zigai/interfacy/blob/main/LICENSE)

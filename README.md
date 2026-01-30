# Interfacy

[![Tests](https://github.com/zigai/interfacy/actions/workflows/tests.yml/badge.svg)](https://github.com/zigai/interfacy/actions/workflows/tests.yml)
[![PyPI version](https://badge.fury.io/py/interfacy.svg)](https://badge.fury.io/py/interfacy)
![Supported versions](https://img.shields.io/badge/python-3.10+-blue.svg)
[![Downloads](https://static.pepy.tech/badge/interfacy)](https://pepy.tech/project/interfacy)
[![license](https://img.shields.io/github/license/zigai/interfacy.svg)](https://github.com/zigai/interfacy/blob/main/LICENSE)

Interfacy is a CLI framework for building command-line interfaces from Python functions, classes, and class instances using type annotations and docstrings.

## Features

- Generate CLIs from functions, class methods, or class instances.
- Nested subcommands and command groups with aliases.
- Type inference from annotations, with support for custom parsers.
- `--help` text generated from docstrings.
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

## Classes as flags

```python
from dataclasses import dataclass
from interfacy import Argparser

@dataclass
class Address:
    """Mailing address data for a user.

    Args:
        city: City name.
        zip: Postal or ZIP code.
    """
    city: str
    zip: int

@dataclass
class User:
    """User profile information for the CLI.

    Args:
        name: Display name.
        age: Age in years.
        address: Optional mailing address details.
    """
    name: str
    age: int
    address: Address | None = None

def greet(user: User) -> str:
    if user.address is None:
        return f"Hello {user.name}, age {user.age}"
    return f"Hello {user.name}, age {user.age} from {user.address.city} {user.address.zip}"

if __name__ == "__main__":
    Argparser(print_result=True).run(greet)
```

Help output:

```text
usage: app.py greet [--help] --user.name USER.NAME --user.age USER.AGE
                    [--user.address.city] [--user.address.zip]

options:
  --help                      show this help message and exit
  --user.name                 Display name. [type: str] (*)
  --user.age                  Age in years. [type: int] (*)
  --user.address.city         City name. [type: str]
  --user.address.zip          Postal or ZIP code. [type: int]
```

## Class-based commands

```python
from interfacy import Argparser

class Calculator:
    def add(self, a: int, b: int) -> int:
        return a + b

    def mul(self, a: int, b: int) -> int:
        return a * b

if __name__ == "__main__":
    Argparser(print_result=True).run(Calculator)
```

## Decorator-based commands

```python
from interfacy import Argparser

parser = Argparser()

@parser.command()
def greet(name: str) -> str:
    return f"Hello, {name}!"

@parser.command(name="calc", aliases=["c"])
class Calculator:
    def add(self, a: int, b: int) -> int:
        return a + b

    def mul(self, a: int, b: int) -> int:
        return a * b

if __name__ == "__main__":
    parser.run()
```

## License

[MIT License](https://github.com/zigai/interfacy/blob/main/LICENSE)

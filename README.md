# Interfacy

[![PyPI version](https://badge.fury.io/py/interfacy.svg)](https://badge.fury.io/py/interfacy)
![Supported versions](https://img.shields.io/badge/python-3.10+-blue.svg)
[![Downloads](https://static.pepy.tech/badge/interfacy)](https://pepy.tech/project/interfacy)
[![license](https://img.shields.io/github/license/zigai/interfacy.svg)](https://github.com/zigai/interfacy/blob/main/LICENSE)

Interfacy is a library for automatically generating CLI applications from Python functions, methods, classes, or instances using their type annotations and docstrings.

## Features

- CLI generation from functions, methods, classes, or instances.
- Argument type inference from annotations.
- Required parameters as positionals or flags.
- Subcommands with optional aliases.
- Multiple help text themes.
- Stdin piping support.
- Optional tab completion via argcomplete.
- Support for user-defined type parsers.

## Installation

### From PyPI

```bash
pip install interfacy
```

```bash
uv add interfacy
```

### From Source

```bash
pip install git+https://github.com/zigai/interfacy.git
```

```bash
uv add "git+https://github.com/zigai/interfacy.git"
```

## Example

```python
def greet(name: str, times: int = 1) -> None:
    for _ in range(times):
        print(f"Hello, {name}!")

if __name__ == "__main__":
    from interfacy import Argparser
    Argparser(print_result=True).run(greet)
```

## License

[MIT License](https://github.com/zigai/interfacy/blob/main/LICENSE)

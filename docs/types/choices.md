# Choices

`Literal` and `Enum` define a fixed set of valid values for a parameter.

## Literal choices

```python
from typing import Literal

Mode = Literal["fast", "safe"]


def deploy(mode: Mode = "safe") -> str:
    """Deploy with a selected mode."""
    return mode
```

```console
$ python app.py --mode fast
$ python app.py --mode safe
```

Invalid values fail during parsing, before the command is called.

Literal choices also appear in help output.

## Required choice flags

Choices work for required parameters too.

```python
def render(format: Literal["json", "yaml"]): ...
```

With the default flag strategy, required non-boolean parameters are positional:

```console
$ python app.py json
```

With keyword-only style, they become required flags:

```console
$ python app.py --format json
```

## Enum choices

Enums pass domain values to the callable instead of raw strings.

```python
from enum import Enum


class Color(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3


def paint(color: Color) -> Color:
    return color
```

```console
$ python app.py RED
```

The callable receives `Color.RED`.

## Optional choices

Optional choices are supported with `T | None`.

```python
def filter_status(status: Literal["open", "closed"] | None = None) -> None: ...
```

```console
$ python app.py
$ python app.py --status open
```

## Help output

Layouts decide how choices are displayed. Some show choices inline, while others align them in a metadata column. See {doc}`../help/layouts` for the available layout presets.

# argparse

The argparse backend is the default backend.

```python
from interfacy import Interfacy

Interfacy(backend="argparse").run(main)
```

It builds on Python's standard `argparse` module and Interfacy's custom help formatter.

## Features

The argparse backend provides:

- no required Click dependency
- standard-library parser behavior
- `@file` argument expansion
- `argcomplete` integration
- Interfacy's full help-layout system
- access to the underlying `ArgumentParser`

## Backend parser

`build_parser()` returns the backend parser object.

```python
parser = Interfacy()
parser.add_command(main)
argparse_parser = parser.build_parser()
print(argparse_parser.format_help())
```

This is useful for tests, documentation snapshots, or integration with existing parser code.

## Formatter class

The argparse backend accepts `formatter_class` when you need a custom `argparse.HelpFormatter` subclass.

```python
import argparse
from interfacy import Interfacy

Interfacy(
    backend="argparse",
    formatter_class=argparse.RawDescriptionHelpFormatter,
).run(main)
```

For most users, `help_layout=` is the preferred customization surface.

## Independent parser

If you do not want callable-derived commands, use Interfacy's argparse-compatible wrapper directly. See {doc}`argparse-wrapper`.

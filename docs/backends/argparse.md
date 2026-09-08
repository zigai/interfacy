# argparse

The argparse backend is the default backend.

```python
from interfacy import Interfacy

Interfacy(backend="argparse").run(main)
```

It builds on Python's standard `argparse` module and Interfacy's shared help renderer.

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

## Help customization

Use `help_layout` to select a layout for generated help:

```python
from interfacy import Interfacy
from interfacy.help import Aligned

Interfacy(
    backend="argparse",
    help_layout=Aligned(),
).run(main)
```

Use `help_renderer` to customize the final rendering of structured help content. Both
customization surfaces are shared with the Click backend. See {doc}`../help/layouts`.

## Independent parser

If you do not want callable-derived commands, use Interfacy's argparse-compatible wrapper directly. See {doc}`argparse-wrapper`.

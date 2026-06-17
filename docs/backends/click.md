# Click

Interfacy can use Click as its backend.

Install the optional dependency:

```console
$ python -m pip install "interfacy[click]"
```

Then select the backend:

```python
from interfacy import Interfacy

Interfacy(backend="click").run(main)
```

## Click command objects

The Click backend builds Click command objects behind the Interfacy API.

The public Interfacy code can stay the same:

```python
def greet(name: str) -> str:
    """Return a greeting."""
    return f"Hello, {name}!"


Interfacy(backend="click", print_result=True).run(greet)
```

## Backend parser

`build_parser()` returns the Click command object for the built CLI.

```python
parser = Interfacy(backend="click")
parser.add_command(greet)
click_command = parser.build_parser()
```

## Differences

The Interfacy API is shared, but the backend libraries have different error types and parsing details.

`formatter_class` is argparse-specific and cannot be used with `backend="click"`.

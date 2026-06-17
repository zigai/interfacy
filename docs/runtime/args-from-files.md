# Args from Files

The argparse backend can expand arguments from files.

Interfacy enables this by default for callable-based parsers.

```python
from interfacy import Interfacy


def greet(name: str) -> str:
    """Return a greeting."""
    return f"Hello, {name}!"


Interfacy(print_result=True).run(greet)
```

Create a file with one argument value:

```text
Ada
```

Then pass it with `@`:

```console
$ python app.py @args.txt
Hello, Ada!
```

## Disable expansion

`allow_args_from_file=False` treats `@value` literally.

```python
Interfacy(
    allow_args_from_file=False,
    print_result=True,
).run(greet)
```

## Manual argparse wrapper

When using `interfacy.argparse_backend.ArgumentParser` directly, use the standard `fromfile_prefix_chars` argument.

```python
from interfacy.argparse_backend import ArgumentParser

parser = ArgumentParser(fromfile_prefix_chars="@")
parser.add_argument("value")
```

`fromfile_prefix_chars=None` disables file expansion.

## Expansion scope

Argument files expand before normal parsing. The `@` prefix is interpreted as a file reference unless argument-file expansion is disabled.

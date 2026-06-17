# Argparse Wrapper

Interfacy's `ArgumentParser` is an argparse-compatible parser with Interfacy help rendering and a few parser conveniences.

It keeps the regular argparse workflow: create a parser, call `add_argument()`, and parse arguments. The wrapper adds Interfacy layouts and colors, custom help flags, and nested destination handling.

```python
from interfacy.argparse_backend import ArgumentParser


parser = ArgumentParser(
    prog="deploy",
    description="Deploy an application build.",
)
parser.add_argument("environment", choices=("staging", "production"))
parser.add_argument("-r", "--region", default="us-east-1")
parser.add_argument("-j", "--jobs", type=int, default=4)
parser.add_argument("--dry-run", action="store_true")

args = parser.parse_args()
print(args)
```

You still call `add_argument()` yourself. Interfacy changes the parser behavior only where the wrapper documents extra options.

## Layouts

Pass `help_layout=` to style manual argparse help.

```python
from interfacy.appearance import ClapLayout
from interfacy.argparse_backend import ArgumentParser

parser = ArgumentParser(
    prog="deploy",
    description="Deploy an application build.",
    help_layout=ClapLayout(),
)
```

## Help column

`help_position` sets a stable description column.

```python
parser = ArgumentParser(
    prog="deploy",
    help_position=32,
)
```

This is useful when option names are long and you want help text to stay aligned.

## Help flags

Customize help aliases with `help_flags`.

```python
parser = ArgumentParser(help_flags=("--help", "-h"))
```

## Args from files

The standard argparse option controls file expansion.

```python
parser = ArgumentParser(fromfile_prefix_chars="@")
```

See {doc}`../runtime/args-from-files`.

## Nested destinations

`nest_dir=` places parsed values under a nested namespace.

```python
parser = ArgumentParser(nest_dir="server")
parser.add_argument("--host")

args = parser.parse_args(["--host", "localhost"])
assert args.server.host == "localhost"
```

Subparser values are nested under the selected subcommand name. This keeps arguments from different command levels separate in the parsed namespace.

## Scope

`ArgumentParser` is for manually defined parsers. It does not inspect Python callables or build commands from signatures.

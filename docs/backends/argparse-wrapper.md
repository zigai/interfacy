# Argparse Wrapper

Interfacy's `ArgumentParser` is an argparse-compatible parser with Interfacy help rendering and a few parser conveniences.

It keeps the regular argparse workflow: create a parser, call `add_argument()`, and parse arguments. The wrapper adds Interfacy layouts and colors, custom help flags, and nested destination handling.

```python
from interfacy.backends.argparse import ArgumentParser


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
from interfacy.help import ClapLayout
from interfacy.backends.argparse import ArgumentParser

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

## Exiting

Like argparse, the parser prints help and exits with status 0, and reports usage errors on stderr and exits with status 2. Pass `sys_exit_enabled=False` to handle these yourself: help raises `InterfacyExit` and usage errors raise `UsageError`. Subparsers inherit the setting.

```python
from interfacy.exceptions import InterfacyExit, UsageError

parser = ArgumentParser(prog="deploy", sys_exit_enabled=False)
parser.add_argument("environment")

try:
    args = parser.parse_args()
except InterfacyExit:
    ...
except UsageError as exc:
    print(exc.usage, exc)
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

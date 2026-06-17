# Exec Flags

Executable flags are zero-argument flags that run a handler and short-circuit normal command execution.

They are useful for flags like `--version`, `--list`, or `--print-config`.

```python
from interfacy import ExecutableFlag, Interfacy


def version() -> str:
    return "demo 1.0.0"


def run(name: str) -> str:
    """Run the main command."""
    return f"hello {name}"


parser = Interfacy(
    print_result=True,
    executable_flags=[
        ExecutableFlag(("--version", "-V"), version, help="Show version."),
    ],
)
parser.run(run)
```

```console
$ python app.py --version
demo 1.0.0
```

The command is not executed when the executable flag is present.

## Command-level flags

Executable flags can also live on a specific command or group.

```python
parser.add_command(
    run,
    executable_flags=[ExecutableFlag("--example", lambda: "example")],
)
```

A group-level executable flag can answer before a missing subcommand error, which is useful for help-like or metadata-like flags.

## Rules

Executable flag handlers must accept no arguments.

```python
def handler() -> str:
    return "ok"
```

`--help` is reserved for help output and cannot be reused as an executable flag.

`display_result=False` suppresses result printing when the handler prints its own output:

```python
ExecutableFlag("--doctor", doctor, display_result=False)
```

`exit_code=` sets a non-zero process code for the flag.

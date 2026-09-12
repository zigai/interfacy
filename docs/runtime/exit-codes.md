# Exit codes

Command return values are data, not process exit codes. A command that returns normally
always exits with `SUCCESS` (`0`), even when it returns a non-zero integer.

```python
from interfacy import Interfacy


def count() -> int:
    return 7


Interfacy(print_result=True).run(count)
```

This prints `7` and exits with code `0`.

## Codes

Exit codes are available from `interfacy.ExitCode`.

| Name | Code | Meaning |
| --- | ---: | --- |
| `SUCCESS` | 0 | Command completed, or help/version exited normally |
| `COMMAND_FAILED` | 1 | The selected command raised an exception |
| `USAGE` | 2 | Command-line input could not be parsed |
| `INTERNAL` | 70 | An unexpected Interfacy/backend invariant failed |
| `CONFIGURATION` | 78 | Command schema, setup, or plugin configuration is invalid |
| `INTERRUPTED` | 130 | The command was interrupted with Ctrl-C |

Let Interfacy manage process exits. Do not pass the result of `run()` to `SystemExit` or
otherwise treat an integer result as an exit code.

## Embedding and tests

Use `invoke()` when embedding Interfacy in another Python process:

```python
parser = Interfacy()
result = parser.invoke(count, args=[])

assert result == 7
```

The compatibility option `Interfacy(sys_exit_enabled=False)` also prevents `run()` from
terminating the process for applications written against Interfacy 0.7. Prefer `invoke()` in
new code because it states the embedded boundary directly.

`invoke()` never renders failures or terminates the process. Parsing, configuration,
plugin, and command failures are raised as exceptions. A command that explicitly raises
`SystemExit` still propagates that exception because it is part of the command's behavior.

Use `await parser.invoke_async(...)` when a command may return an awaitable while an event
loop is already running. `run()` is the CLI boundary: it renders configured output and
errors, maps failures to `ExitCode`, and always raises `SystemExit`.

For full tracebacks during CLI development, set `full_error_traceback=True`.

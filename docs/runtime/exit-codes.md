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

Exit codes are available from `interfacy.core.ExitCode`.

| Name | Code | Meaning |
| --- | ---: | --- |
| `SUCCESS` | 0 | Command completed, or help/version exited normally |
| `ERR_INVALID_ARGS` | 1 | Invalid entrypoint target or arguments |
| `ERR_PARSING` | 2 | Parser construction or CLI parsing failed |
| `ERR_RUNTIME` | 3 | The command raised an exception |
| `ERR_RUNTIME_INTERNAL` | 4 | An internal runtime failure occurred |
| `INTERRUPTED` | 130 | The command was interrupted with Ctrl-C |

Let Interfacy manage process exits. Do not pass the result of `run()` to `SystemExit` or
otherwise treat an integer result as an exit code.

## Embedding and tests

Set `sys_exit_enabled=False` only when the host needs to inspect the result without exiting:

```python
parser = Interfacy(sys_exit_enabled=False)
result = parser.run(count, args=[])

assert result == 7
```

A successful run returns the command value; a failed or interrupted run returns its
exception object. Use `isinstance(result, BaseException)` to distinguish failures, and avoid
returning exception objects as command data.

A command that raises `SystemExit` keeps its explicit exit code. With process exits disabled,
the `SystemExit` object is returned instead.

For full tracebacks during development, set `full_error_traceback=True`.

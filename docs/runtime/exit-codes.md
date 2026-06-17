# Exit Codes

Interfacy separates command return values from process exit codes.

A command can return `0` as normal data. That does not mean “exit successfully.”

```python
def count() -> int:
    return 0
```

With `print_result=True`, the returned value is displayed.

## Built-in codes

Interfacy uses these process-level codes:

| Name | Code | Meaning |
| --- | ---: | --- |
| `SUCCESS` | 0 | command completed or help/version exited normally |
| `ERR_INVALID_ARGS` | 1 | invalid entrypoint target or entrypoint arguments |
| `ERR_PARSING` | 2 | parser construction or CLI parse failure |
| `ERR_RUNTIME` | 3 | user command raised an exception |
| `ERR_RUNTIME_INTERNAL` | 4 | Interfacy runtime/internal failure |
| `INTERRUPTED` | 130 | keyboard interrupt |

They are available as `interfacy.core.ExitCode`.

## sys.exit behavior

By default, parser exits use `sys.exit`.

For tests and embedded use, disable process exits:

```python
from interfacy import Interfacy

parser = Interfacy(sys_exit_enabled=False)
result = parser.run(main, args=["--help"])
```

This lets you inspect the result instead of terminating the process.

## Tracebacks

Runtime failures normally produce concise CLI errors. Enable full tracebacks while developing:

```python
Interfacy(full_error_traceback=True).run(main)
```

## SystemExit from commands

If your command raises `SystemExit`, Interfacy respects it. This preserves existing command behavior when wrapping older code.

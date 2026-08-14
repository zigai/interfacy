# Interrupts

Interfacy handles `KeyboardInterrupt` so CLIs can stop cleanly.

```python
from interfacy import Interfacy

Interfacy().run(main)
```

When the user presses Ctrl-C, Interfacy maps the interruption to the interrupted exit code and avoids treating it like a normal command failure.

## Silent interrupts

Interrupt logging is silent by default.

```python
Interfacy(silent_interrupt=True).run(main)
```

Set `silent_interrupt=False` when you want a visible message.

```python
Interfacy(silent_interrupt=False).run(main)
```

## Interrupt callbacks

`on_interrupt` handles cleanup or telemetry.

```python
def handle_interrupt(exc: KeyboardInterrupt) -> None:
    print("cancelled")


Interfacy(on_interrupt=handle_interrupt).run(main)
```

Keep callbacks quick and safe. They run while the process is already being interrupted.

## Embedding

`invoke()` and `invoke_async()` propagate `KeyboardInterrupt` unchanged. They do not render
an interrupt message or invoke process-boundary callbacks:

```python
result = Interfacy().invoke(main, args=[])
```

Use `run()` when Interfacy owns the CLI process. At that boundary, `on_interrupt` runs,
the configured interrupt message is rendered, and the process exits with code `130`.

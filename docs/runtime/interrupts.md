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

## Reraising

`reraise_interrupt=True` passes the original interrupt to an embedding application or test harness.

```python
Interfacy(
    on_interrupt=handle_interrupt,
    reraise_interrupt=True,
).run(main)
```

## Signal handling

Interfacy installs its runtime signal handling only when running on the main thread. Non-main-thread use avoids replacing process-wide signal handlers.

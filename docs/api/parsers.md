# Parsers

`Interfacy` is the supported programmatic entry point.

- `invoke()` executes synchronously without rendering or process exits.
- `invoke_async()` executes and awaits asynchronous results inside an existing event loop.
- `run()` is the CLI boundary; it renders results or failures and raises `SystemExit`.

```python
from interfacy import Interfacy

result = Interfacy().invoke(main, args=[])
```

```{eval-rst}
.. autoclass:: interfacy.Interfacy
   :members:
   :exclude-members: __init__
```

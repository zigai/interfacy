# Parsers

`Interfacy` is the programmatic entry point. It defaults to the argparse
backend. Pass `backend="click"` when you want Click integration.

## Interfacy

```python
from interfacy import Interfacy

Interfacy(print_result=True).run(main)
Interfacy(backend="click", print_result=True).run(main)
```

```{eval-rst}
.. autoclass:: interfacy.Interfacy
   :members:
   :exclude-members: __init__
```

# Annotations

Interfacy uses type annotations to convert command-line strings into Python values.

```python
def report(path: str, limit: int = 10, ratio: float = 0.5) -> None:
    ...
```

```console
$ python app.py data.csv --limit 20 --ratio 0.8
```

The callable receives `path` as `str`, `limit` as `int`, and `ratio` as `float`.

## Common shapes

| Annotation | CLI behavior |
| --- | --- |
| `str` | string value |
| `int` / `float` | numeric conversion |
| `bool` | flag behavior |
| `Path` | path-like value |
| `list[T]` | repeated values converted as `T` |
| `tuple[A, B]` | fixed number of values converted per element |
| `Literal[...]` | choice validation |
| `Enum` | choice validation |
| `T \| None` | optional value |
| dataclass / Pydantic / plain class | structured model flags |

Out of the box, Interfacy also parses a few standard-library types: {class}`datetime.date`, {class}`datetime.datetime`, {class}`datetime.time`, {class}`datetime.timedelta`, {class}`decimal.Decimal`, {class}`fractions.Fraction`, {class}`dict`, {class}`range`, and {class}`slice`.

## Missing annotations

An untyped parameter is accepted. CLI input for it is passed through as `str`, so Interfacy cannot do type-specific conversion or help formatting for it.

```python
def echo(value):
    return value
```

Annotations make parsing predictable and help output more specific.

## Optional values

`T | None` marks a value as optional.

```python
def find(name: str | None = None) -> str | None:
    return name
```

```console
$ python app.py
$ python app.py --name Ada
```

Optional list values work too:

```python
def tags(items: list[str] | None = None) -> list[str] | None:
    return items
```

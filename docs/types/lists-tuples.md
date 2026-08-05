# Lists & Tuples

Repeated values are described with collection annotations.

## Lists

A required list consumes one or more values.

```python
def collect(tags: list[str]) -> list[str]:
    return tags
```

```console
$ python app.py backend api urgent
```

The command receives:

```python
["backend", "api", "urgent"]
```

If the parser uses keyword-only style, the same parameter is provided through a flag:

```console
$ python app.py --tags backend api urgent
```

## Typed lists

List elements are converted using the element annotation.

```python
def total(values: list[int]) -> int:
    return sum(values)
```

```console
$ python app.py 1 2 3
```

The callable receives `[1, 2, 3]`.

## Optional lists

`list[T] | None = None` makes the whole list optional.

```python
def search(tags: list[str] | None = None) -> list[str] | None:
    return tags
```

```console
$ python app.py
$ python app.py --tags api backend
```

## Fixed tuples

A fixed tuple consumes exactly the number of values in the annotation.

```python
def pair(items: tuple[int, str]) -> tuple[int, str]:
    return items
```

```console
$ python app.py 123 hello
```

The callable receives `(123, "hello")`.

## Lists of tuples

A list of fixed tuples groups flat CLI values.

```python
def rows(items: list[tuple[int, str]]) -> list[tuple[int, str]]:
    return items
```

```console
$ python app.py 1 alpha 2 beta
```

The callable receives:

```python
[(1, "alpha"), (2, "beta")]
```

## Variadic args

`*args` works like a variable-length positional list.

```python
def archive(service: str, *paths: str) -> tuple[str, tuple[str, ...]]:
    return service, paths
```

```console
$ python app.py payments app.log db.log
```

Keyword-only options can follow varargs:

```python
def search(query: str, *paths: str, ignore_case: bool = False) -> None: ...
```

```console
$ python app.py timeout app.log db.log --ignore-case
```

`**kwargs` can be supplied as a mapping value, usually a JSON object.

# Booleans

Boolean parameters become flags.

```python
def sync(verbose: bool = False, cache: bool = True) -> None:
    ...
```

```console
$ python app.py --verbose
$ python app.py --no-cache
```

## Default false

A boolean with `False` as the default is enabled by passing the positive flag.

```python
def build(verbose: bool = False) -> bool:
    return verbose
```

```console
$ python app.py
$ python app.py --verbose
```

## Default true

A boolean with `True` as the default can be disabled with a generated negative flag.

```python
def build(cache: bool = True) -> bool:
    return cache
```

```console
$ python app.py
$ python app.py --no-cache
```

The negative prefix defaults to `no-`.

## Required booleans

A required boolean accepts both forms.

```python
def set_enabled(enabled: bool) -> bool:
    return enabled
```

```console
$ python app.py --enabled
$ python app.py --no-enabled
```

## Negative-looking names

Some boolean names already sound negative:

```python
def sync(disable_cache: bool = False) -> None:
    ...
```

By default, Interfacy treats these as one-way flags:

```console
$ python app.py --disable-cache
```

It does not generate a confusing inverse like `--cache` unless you opt into dual mode.

```python
Interfacy(
    negative_bool_name_mode="dual",
).run(sync)
```

Negative-looking prefixes default to:

- `no-`
- `disable-`
- `without-`

Configure them with `negative_bool_name_prefixes=`.

## Custom negative prefix

`bool_negative_prefix` changes generated negative flag names.

```python
Interfacy(bool_negative_prefix="without-").run(build)
```

```console
$ python app.py --without-cache
```

Set `bool_negative_prefix=None` to disable generated negative aliases.

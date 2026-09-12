# Booleans

Boolean parameters become flags. Interfacy exposes only forms that can change a
defaulted value, while required and tri-state booleans accept both forms.

## Default false

A false-default boolean exposes its positive form.

```python
def build(verbose: bool = False) -> bool:
    return verbose
```

```console
$ python app.py --verbose
```

Omitting the flag passes `False`; `--verbose` passes `True`. Interfacy does not
generate a redundant `--no-verbose` form.

## Default true

A true-default boolean exposes its negative form.

```python
def build(cache: bool = True) -> bool:
    return cache
```

```console
$ python app.py --no-cache
```

Omitting the flag passes `True`; `--no-cache` passes `False`. The positive
`--cache` form is omitted because it only restates the default.

## Required and tri-state booleans

A required boolean accepts both values explicitly.

```python
def set_enabled(enabled: bool) -> bool:
    return enabled
```

```console
$ python app.py --enabled
$ python app.py --no-enabled
```

A boolean with a `None` default is also dual-form. Omitting it preserves `None`,
while its positive and negative forms pass `True` and `False` respectively.

## Explicit modes

Use `Param.boolean_mode` when the callable default does not express the desired
CLI surface.

```python
from interfacy import Interfacy, Param


def render(*, color: bool = False) -> bool:
    return color


parser = Interfacy()
parser.add_command(
    render,
    parameter_settings={"color": Param(boolean_mode="dual")},
)
parser.run()
```

Available modes are:

- `auto`: false defaults are positive-only, true defaults are negative-only,
  and required or `None`-default booleans are dual-form.
- `dual`: expose forms that set both `True` and `False`.
- `positive_only`: expose only flags that set `True`; the parameter must default
  to `False`.
- `negative_only`: expose only flags that set `False`; the parameter must default
  to `True`.

## Custom negative flags

Generated negative flags use the `no-` prefix. Supply `Param.negative_flags`
when an explicit inverse reads better.

```python
def sync(*, disable_cache: bool = False) -> bool:
    return disable_cache


parser.add_command(
    sync,
    parameter_settings={
        "disable_cache": Param(
            boolean_mode="dual",
            negative_flags="--enable-cache",
        )
    },
)
```

This exposes `--disable-cache` to pass `True` and `--enable-cache` to pass
`False`.

## Custom generated prefix

`bool_negative_prefix` changes the parser-wide prefix used when a parameter does
not define `negative_flags`.

```python
Interfacy(bool_negative_prefix="without-").run(build)
```

Set `bool_negative_prefix=None` to disable automatically generated inverse flags.

For the true-default `cache` example, this generates `--without-cache`.

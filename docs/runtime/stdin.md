# Stdin

Interfacy can route piped stdin into command parameters.

```python
from interfacy import Interfacy


def echo(message: str) -> str:
    """Echo a message."""
    return message


Interfacy(print_result=True, pipe_targets="message").run(echo)
```

```console
$ echo "hello" | python app.py
hello
```

## Per-command routing

Pipe targets can be configured on a single command.

```python
parser = Interfacy(print_result=True)
parser.add_command(echo, pipe_targets="message")
parser.run()
```

## Multiple targets

When more than one parameter is targeted, stdin is split into chunks. Newlines are the default delimiter.

```python
def pair(left: str, right: str) -> tuple[str, str]:
    return left, right


parser.add_command(pair, pipe_targets=("left", "right"))
```

```console
$ printf "one\ntwo" | python app.py
```

The command receives `("one", "two")`.

## Custom delimiter

A dict configures delimiter and priority settings.

```python
parser.add_command(
    pair,
    pipe_targets={"bindings": ("left", "right"), "delimiter": ","},
)
```

```console
$ printf "one,two" | python app.py
```

`parameters` and `bindings` are both accepted as the target-key name.

## Lists

If the target is a list, piped chunks become list elements.

```python
def collect(items: list[int]) -> list[int]:
    return items


parser.add_command(collect, pipe_targets="items")
```

```console
$ printf "1\n2\n3" | python app.py
```

The command receives `[1, 2, 3]`.

## Priority

CLI values win over stdin by default.

```python
parser.add_command(echo, pipe_targets="message")
```

```console
$ echo piped | python app.py cli
```

The command receives `"cli"`.

`priority="pipe"` makes stdin override explicit CLI values.

```python
parser.add_command(
    echo,
    pipe_targets={"bindings": "message", "priority": "pipe"},
)
```

## Partial chunks

By default, Interfacy reports an error if fewer chunks are provided than required targets. With `allow_partial=True`, missing chunks become `None` and are ignored for optional parameters.

```python
parser.add_command(
    pair,
    pipe_targets={"bindings": ("left", "right"), "allow_partial": True},
)
```

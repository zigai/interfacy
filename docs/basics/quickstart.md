# Quickstart

Install Interfacy:

```bash
pip install interfacy
```

or:

```bash
uv add interfacy
```

Put a typed function in `app.py`:

```python
from interfacy import Interfacy


def greet(name: str, times: int = 1, excited: bool = False) -> str:
    """
    Print a greeting.

    Args:
        name: Person to greet.
        times: Number of greetings.
        excited: Use exclamation marks.
    """
    mark = "!" if excited else "."
    return "\n".join(f"Hello, {name}{mark}" for _ in range(times))


if __name__ == "__main__":
    Interfacy(print_result=True).run(greet)
```

Run it:

```text
$ python app.py Ada --times 2 --excited
Hello, Ada!
Hello, Ada!
```

Ask for help:

```text
$ python app.py --help
```

Interfacy uses the function signature as the CLI contract:

- `name` is required, so it becomes a positional argument.
- `times` has a default, so it becomes an option.
- `excited` is a boolean, so it becomes a flag.
- the docstring becomes command and option help.

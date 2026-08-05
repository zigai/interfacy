# Models

Structured parameters let one Python object expand into several CLI flags.

Interfacy can expand:

- dataclasses
- Pydantic models
- plain classes with typed `__init__` parameters

## Dataclasses

```python
from dataclasses import dataclass
from interfacy import Interfacy


@dataclass
class Address:
    city: str
    postal_code: int


@dataclass
class User:
    name: str
    age: int
    address: Address | None = None


def greet(user: User) -> str:
    return f"Hello {user.name}, age {user.age}"


Interfacy(print_result=True).run(greet)
```

```console
$ python app.py --user.name Ada --user.age 32
Hello Ada, age 32
```

Nested fields use dot-separated flags by default:

```console
$ python app.py \
    --user.name Ada \
    --user.age 32 \
    --user.address.city London \
    --user.address.postal-code 12345
```

The callable receives a real `User` instance.

## Optional models

An optional model becomes `None` when none of its fields are provided.

```python
def maybe_user(user: User | None = None) -> str:
    return "none" if user is None else user.name
```

If any nested field is provided, Interfacy reconstructs the model and validates required fields.

## Model defaults

If a model parameter has a default instance, Interfacy starts with that default and merges CLI overrides into it.

```python
DEFAULT_USER = User(name="guest", age=0)


def greet(user: User = DEFAULT_USER) -> str:
    return user.name
```

```console
$ python app.py --user.name Ada
```

## Plain classes

A plain class can be expanded when its initializer is typed.

```python
class Server:
    def __init__(self, host: str, port: int = 8000) -> None:
        self.host = host
        self.port = port


def connect(server: Server) -> None: ...
```

```console
$ python app.py --server.host localhost --server.port 9000
```

## Pydantic models

Pydantic models are expanded using their fields and reconstructed before execution. Pydantic validation still belongs to the model.

## Configuration

Model expansion is enabled by default.

```python
Interfacy(expand_model_params=False).run(greet)
```

Limit nesting with `model_expansion_max_depth`:

```python
Interfacy(model_expansion_max_depth=2).run(greet)
```

Change the nested separator with a flag strategy:

```python
from interfacy.naming import DefaultFlagStrategy

Interfacy(
    flag_strategy=DefaultFlagStrategy(nested_separator="__"),
).run(greet)
```

```console
$ python app.py --user__name Ada --user__age 32
```

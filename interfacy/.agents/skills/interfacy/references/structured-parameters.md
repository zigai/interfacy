# Structured Parameters

Use structured parameters when a command has a meaningful group of inputs, not just because nesting is possible.

## When To Use Them

Good fit:

- User/profile/config options that are often passed together.
- Repeated command patterns that would otherwise duplicate many flags.
- Existing Pydantic or dataclass inputs that already describe the command boundary.

Poor fit:

- Huge domain models with many fields unrelated to the CLI.
- Deep object graphs that make flags hard to type.
- Values that users naturally provide as one file or one string.

## Prefer CLI-Sized Models

Create small models for the CLI when the domain object is too broad.

```python
from dataclasses import dataclass

from interfacy import Interfacy

@dataclass
class UserInput:
    name: str
    age: int

def create_user(user: UserInput, *, active: bool = True) -> str:
    """Create a user.

    Args:
        user: User details.
        active: Whether the user starts active.

    Returns:
        Created user name.
    """
    return user.name

Interfacy(print_result=True).run(create_user)
```

Users get grouped flags such as:

```text
--user.name Ada --user.age 32
```

## Design Rules

- Keep nesting shallow.
- Give fields user-facing names.
- Put defaults on optional fields.
- Use `T | None` for optional nested objects.
- Prefer dataclasses for CLI-only inputs.
- Use Pydantic when validation already matters at this boundary.

If the generated flag names feel awkward, that is usually a sign the model is not a good CLI shape. Add a small adapter model instead of exposing the domain model directly.

## Refactoring With Structured Inputs

When migrating an old CLI, preserve existing flag names where users rely on them. Structured parameters are useful only if they improve clarity without breaking compatibility.

If compatibility matters more than grouping, keep a flat function signature.

## Tests

Test that the command reconstructs the expected object, not just that parsing succeeds:

```python
parser = Interfacy(sys_exit_enabled=False)
result = parser.run(create_user, args=["--user.name", "Ada", "--user.age", "32"])
```

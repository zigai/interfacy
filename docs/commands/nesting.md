# Nesting

Nested commands let a CLI grow without flattening every operation into the top level.

Classes create one level of nesting automatically:

```python
class Workspace:
    """Workspace commands."""

    def open_task(self, task_id: str) -> str:
        """Open a task."""
        return f"open {task_id}"

    def close_task(self, task_id: str) -> str:
        """Close a task."""
        return f"close {task_id}"
```

```console
$ python app.py workspace open-task TASK-123
$ python app.py workspace close-task TASK-123
```

Manual groups can be nested explicitly:

```python
from interfacy import CommandGroup, Interfacy


def sync_users() -> str:
    """Sync user records."""
    return "synced"


admin = CommandGroup("admin", description="Administrative commands")
admin.add_command(sync_users)

workspace = CommandGroup("workspace", description="Workspace commands")
workspace.add_group(admin)

Interfacy(print_result=True).run(workspace)
```

```console
$ python app.py workspace admin sync-users
synced
```

## Nested command paths

Nested paths add context to command names:

- `workspace open-task`
- `workspace admin sync-users`
- `db query`
- `release cut`

Top-level commands remain flat unless they are added under a class or group.

## Help at every level

Every command node can render help.

```console
$ python app.py --help
$ python app.py workspace --help
$ python app.py workspace admin --help
```

Descriptions come from docstrings or explicit `description=` values.

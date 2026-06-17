# Help Groups

Help groups organize command listings without changing command routing.

```python
from interfacy import Interfacy


def clone(url: str) -> str:
    """Clone a repository."""
    return url


def status() -> str:
    """Show working tree status."""
    return "clean"


parser = Interfacy(description="Repository tools")
parser.add_command(clone, help_group="start a working area:")
parser.add_command(status, help_group="inspect state:")
parser.run()
```

Help output groups the rows under those headings. The commands still run the same way:

```console
$ python repo.py clone https://example.com/repo.git
$ python repo.py status
```

## Decorators

`help_group` is available on decorator registration too.

```python
parser = Interfacy()


@parser.command(help_group="inspect state:")
def status() -> str:
    """Show working tree status."""
    return "clean"
```

## Command groups

Manual groups and subgroups can use help groups.

```python
from interfacy import CommandGroup

workspace = CommandGroup("workspace", description="Workspace commands")
workspace.add_command(open_task, help_group="tasks:")
workspace.add_command(close_task, help_group="tasks:")

admin = CommandGroup("admin", description="Admin commands")
workspace.add_group(admin, help_group="administration:")
```

## Group label text

A group label is rendered as a small section heading:

```text
start a working area:
inspect state:
administration:
```

Keep labels short. They are part of the help surface.

## Layout control

Layouts expose `command_indent` and `command_group_spacing` for grouped command listings.

```python
from interfacy.appearance import ArgparseLayout

layout = ArgparseLayout(command_indent=4, command_group_spacing=1)
Interfacy(help_layout=layout).run(main)
```
